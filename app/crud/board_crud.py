import json
from fastapi import Depends, HTTPException
from sqlmodel import select, update, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from app.models.board_model import Board, Board_Comment
from app.models.user_model import RoleType, User
from sqlalchemy.orm import selectinload
from app.core.database.mysql import mysql_manager
from app.core.database.redis import redis_manager
from app.core.logger import logger_manager
from app.core.i18n.i18n import get_message, Language
from app.utils.agent import agent_utils
from app.utils.keyset_pagination import paginator_desc


class BoardCrud:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = logger_manager.get_logger(__name__)

    async def _build_board_comment_tree(
        self, comments: List[Board_Comment], parent_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        tree = []
        for comment in comments:
            if comment.parent_id == parent_id:
                children = await self._build_board_comment_tree(comments, comment.id)

                comment_dict = {
                    "comment_id": comment.id,
                    "user_id": comment.user_id,
                    "username": comment.user.username if comment.user else None,
                    "avatar_url": comment.user.avatar.thumbnail_filepath_url
                    or comment.user.avatar.original_filepath_url
                    if comment.user and comment.user.avatar
                    else None,
                    "user_role": comment.user.role.name,
                    "city": comment.user.city,
                    "parent_id": comment.parent_id,
                    "comment": comment.comment,
                    "created_at": comment.created_at.isoformat()
                    if comment.created_at
                    else None,
                    "updated_at": comment.updated_at.isoformat()
                    if comment.updated_at
                    else None,
                }
                if children:
                    comment_dict["children"] = children
                tree.append(comment_dict)
        return tree

    async def _get_board_by_id(self, board_id: int) -> Optional[Board]:
        statement = select(Board).where(Board.id == board_id)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def _get_board_comment_by_id(
        self, board_comment_id: int
    ) -> Optional[Board_Comment]:
        statement = select(Board_Comment).where(
            Board_Comment.id == board_comment_id)
        result = await self.db.execute(statement)
        return result.scalar_one_or_none()

    async def get_board_details(
        self,
        language: Language,
    ) -> Dict[str, Any]:
        # 获取缓存
        cache_key = f"board_details:lang={language}"
        cache_result = await redis_manager.get_async(cache_key)
        if cache_result:
            return json.loads(cache_result)

        statement = select(Board)
        result = await self.db.execute(statement)
        board = result.scalars().first()

        if not board:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.common.boardNotFound", lang=language),
            )

        response = {
            "board_id": board.id,
            "title": board.chinese_title
            if language == Language.ZH_CN
            else board.english_title,
            "description": board.chinese_description
            if language == Language.ZH_CN
            else board.english_description,
            "created_at": board.created_at.isoformat() if board.created_at else None,
            "updated_at": board.updated_at.isoformat() if board.updated_at else None,
        }

        # 缓存数据
        await redis_manager.set_async(cache_key, json.dumps(response))
        return response

    async def update_board(
        self,
        board_id: int,
        role: RoleType,
        chinese_title: str,
        chinese_description: str,
        language: Language,
    ) -> bool:
        if role != RoleType.admin:
            raise HTTPException(
                status_code=403,
                detail=get_message(
                    key="common.insufficientPermissions", lang=language),
            )

        # check if board exists
        board = await self._get_board_by_id(board_id)
        if not board:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.common.boardNotFound", lang=language),
            )

        # update board
        if board.chinese_title != chinese_title:
            english_title = await agent_utils.translate(text=chinese_title)
        else:
            english_title = board.english_title
        if board.chinese_description != chinese_description:
            english_description = await agent_utils.translate(text=chinese_description)
        else:
            english_description = board.english_description

        # update board
        await self.db.execute(
            update(Board)
            .where(Board.id == board_id)
            .values(
                chinese_title=chinese_title,
                english_title=english_title,
                chinese_description=chinese_description,
                english_description=english_description,
            )
        )
        await self.db.commit()
        await self.db.refresh(board)

        # 更新cache
        await redis_manager.delete_pattern_async("board_details:*")

        return True

    async def create_board_comment(
        self,
        board_id: int,
        user_id: int,
        parent_id: Optional[int],
        comment: str,
        language: Language,
    ) -> bool:
        # 检查board是否存在
        board = await self._get_board_by_id(board_id)
        if not board:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.common.boardNotFound", lang=language),
            )

        # 插入board_comment
        await self.db.execute(
            insert(Board_Comment).values(
                board_id=board_id,
                user_id=user_id,
                parent_id=parent_id,
                comment=comment,
            )
        )
        await self.db.commit()

        # 更新cache
        cache_key = f"board_comment_lists:{board_id}:*"
        await redis_manager.delete_pattern_async(cache_key)

        return True

    async def get_board_comment_lists(
        self,
        board_id: int,
        language: Language,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        cache_key = f"board_comment_lists:{board_id}:{limit}:{cursor}"
        cache_data = await redis_manager.get_async(cache_key)
        if cache_data:
            return json.loads(cache_data)

        # 先获取父评论（parent_id 为 None 的评论）
        parent_statement = (
            select(Board_Comment)
            .options(selectinload(Board_Comment.user).selectinload(User.avatar))
            .where(
                Board_Comment.board_id == board_id,
                Board_Comment.is_deleted == False,
                Board_Comment.parent_id.is_(None),  # 只获取父评论
            )
        )

        # 应用 keyset pagination 过滤到父评论
        if cursor:
            parent_statement = paginator_desc.apply_filters(
                parent_statement, Board_Comment.created_at, Board_Comment.id, cursor
            )

        # 应用排序到父评论
        parent_statement = parent_statement.order_by(
            *paginator_desc.order_by(Board_Comment.created_at, Board_Comment.id)
        )

        # 限制父评论数量
        parent_statement = parent_statement.limit(limit + 1)

        # 获取父评论
        parent_result = await self.db.execute(parent_statement)
        parent_comments = parent_result.scalars().all()

        # 检查是否有更多父评论
        has_next = len(parent_comments) > limit
        if has_next:
            parent_comments = parent_comments[:-1]  # 移除最后一条父评论

        if not parent_comments:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    "board.createBoardComment.commentNotFound", language
                ),
            )

        # 获取所有父评论的子评论和孙评论，确保评论树完整（支持三级嵌套）
        all_comments = list(parent_comments)
        if parent_comments:
            parent_ids = [c.id for c in parent_comments]

            # 第一级：获取子评论（parent_id 指向父评论）
            children_statement = (
                select(Board_Comment)
                .options(selectinload(Board_Comment.user).selectinload(User.avatar))
                .where(
                    Board_Comment.board_id == board_id,
                    Board_Comment.is_deleted == False,
                    Board_Comment.parent_id.in_(parent_ids),
                )
            )

            children_result = await self.db.execute(children_statement)
            children_comments = children_result.scalars().all()
            all_comments.extend(children_comments)

            # 第二级：获取孙评论（parent_id 指向子评论）
            if children_comments:
                children_ids = [c.id for c in children_comments]
                grandchildren_statement = (
                    select(Board_Comment)
                    .options(selectinload(Board_Comment.user).selectinload(User.avatar))
                    .where(
                        Board_Comment.board_id == board_id,
                        Board_Comment.is_deleted == False,
                        Board_Comment.parent_id.in_(children_ids),
                    )
                )

                grandchildren_result = await self.db.execute(grandchildren_statement)
                grandchildren_comments = grandchildren_result.scalars().all()
                all_comments.extend(grandchildren_comments)

                self.logger.info(
                    f"Retrieved {len(parent_comments)} parent comments, {len(children_comments)} child comments, and {len(grandchildren_comments)} grandchild comments"
                )
            else:
                self.logger.info(
                    f"Retrieved {len(parent_comments)} parent comments and {len(children_comments)} child comments"
                )

        # 构建评论树
        comment_tree = await self._build_board_comment_tree(all_comments)

        # 生成下一页的 cursor（基于父评论）
        next_cursor = None
        if has_next and parent_comments:
            last_parent_comment = parent_comments[-1]
            next_cursor = paginator_desc.encode_cursor(
                last_parent_comment.created_at, last_parent_comment.id
            )

        # 使用 keyset paginator 的 create_response_data 方法
        response = paginator_desc.create_response_data(
            items=comment_tree,
            limit=limit,
            has_next=has_next,
            next_cursor=next_cursor,
            items_key="comments",
        )

        # cache the result
        await redis_manager.set_async(cache_key, json.dumps(response))

        return response

    async def update_board_comment(
        self,
        user_id: int,
        board_comment_id: int,
        comment: str,
        language: Language,
    ) -> bool:
        # check if board_comment exists
        board_comment = await self._get_board_comment_by_id(board_comment_id)
        if not board_comment:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.createBoardComment.boardCommentNotFound", lang=language
                ),
            )

        # check if user is the owner of the board_comment
        if board_comment.user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail=get_message(
                    key="common.insufficientPermissions", lang=language),
            )

        # update board_comment
        await self.db.execute(
            update(Board_Comment)
            .where(Board_Comment.id == board_comment_id)
            .values(
                comment=comment,
            )
        )
        await self.db.commit()

        # 更新cache
        cache_key = f"board_comment_lists:{board_comment.board_id}:*"
        await redis_manager.delete_pattern_async(cache_key)

        return True

    async def delete_board_comment(
        self,
        user_id: int,
        role: RoleType,
        board_comment_id: int,
        language: Language,
    ) -> bool:
        # check if board_comment exists
        board_comment = await self._get_board_comment_by_id(board_comment_id)
        if not board_comment:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.createBoardComment.boardCommentNotFound", lang=language
                ),
            )

        # 允许作者或管理员删除，其余情况返回404（与博客评论删除逻辑一致）
        if board_comment.user_id != user_id and role != RoleType.admin:
            raise HTTPException(
                status_code=404,
                detail=get_message(
                    key="board.createBoardComment.boardCommentNotFound", lang=language
                ),
            )

        # delete board_comment
        await self.db.execute(
            delete(Board_Comment).where(Board_Comment.id == board_comment_id)
        )
        await self.db.commit()

        # 更新cache
        cache_key = f"board_comment_lists:{board_comment.board_id}:*"
        await redis_manager.delete_pattern_async(cache_key)

        return True


def get_board_crud(db: AsyncSession = Depends(mysql_manager.get_db)) -> BoardCrud:
    return BoardCrud(db)
