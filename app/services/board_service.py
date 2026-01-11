from fastapi import Depends
from typing import Dict, Any, Optional
from app.crud.board_crud import BoardCrud, get_board_crud
from app.models.user_model import RoleType


class BoardService:
    def __init__(self, board_crud: BoardCrud):
        self.board_crud = board_crud

    async def get_board_details(self) -> Dict[str, Any]:
        return await self.board_crud.get_board_details()

    async def update_board(
        self,
        board_id: int,
        role: RoleType,
        chinese_title: str,
        chinese_description: str,
    ) -> bool:
        return await self.board_crud.update_board(
            board_id=board_id,
            role=role,
            chinese_title=chinese_title,
            chinese_description=chinese_description,
            
        )

    async def create_board_comment(
        self,
        board_id: int,
        user_id: int,
        parent_id: Optional[int],
        comment: str,
    ) -> bool:
        return await self.board_crud.create_board_comment(
            board_id=board_id,
            user_id=user_id,
            parent_id=parent_id,
            comment=comment,
            
        )

    async def get_board_comment_lists(
        self,
        board_id: int,
        limit: int = 20,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self.board_crud.get_board_comment_lists(
            board_id=board_id, limit=limit, cursor=cursor
        )

    async def update_board_comment(
        self,
        user_id: int,
        board_comment_id: int,
        comment: str,
    ) -> bool:
        return await self.board_crud.update_board_comment(
            user_id=user_id,
            board_comment_id=board_comment_id,
            comment=comment,
            
        )

    async def delete_board_comment(
        self,
        user_id: int,
        role: RoleType,
        board_comment_id: int,
    ) -> bool:
        return await self.board_crud.delete_board_comment(
            user_id=user_id,
            board_comment_id=board_comment_id,
            
            role=role,
        )


def get_board_service(
    board_crud: BoardCrud = Depends(get_board_crud),
) -> BoardService:
    return BoardService(board_crud=board_crud)
