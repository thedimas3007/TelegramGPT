import sqlite3

from typing import Optional, List, Union
from datetime import datetime


class Message():
    def __init__(self, message: str, chat_id: int, author: str, created_at: datetime = None, uid: int = -1) -> None:
        self.message = message
        self.chat_id = chat_id
        self.author = author
        self.created_at = created_at if created_at is not None else datetime.now()
        self.uid = uid
    

    def pack(self) -> dict:
        return {
            "role": self.author,
            "content": self.message
        }


class Chat():
    def __init__(self, title: str, owner: int, created_at: datetime = None, last_accessed: datetime = None, uid: int = -1) -> None:
        self.title = title
        self.owner = owner
        self.created_at = created_at if created_at is not None else datetime.now()
        self.last_accessed = last_accessed if last_accessed is not None else datetime.now()
        self.uid = uid


class Database():
    def __init__(self, path: str = "messages.db") -> None:
        self.con = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.cur = self.con.cursor()

        self.cur.execute("""CREATE TABLE IF NOT EXISTS message (
            message TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            author VARCHAR(255) NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT
        );""")
        self.cur.execute("""CREATE TABLE IF NOT EXISTS chat (
            title VARCHAR(255) NOT NULL,
            owner INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            uid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT
        );""")
        self.con.commit()


    def chat_exists(self, uid: int) -> bool:
        self.cur.execute("SELECT * FROM chat WHERE uid = ?", (uid,))
        return len(self.cur.fetchall()) > 0


    def create_chat(self, title: str, owner: int) -> Chat:
        self.cur.execute("INSERT INTO chat (title, owner) VALUES (?, ?)", (title, owner))
        uid = self.cur.lastrowid
        self.con.commit()
        return self.get_chat(uid)


    def store_chat(self, chat: Chat) -> Chat:
        self.create_chat(chat.title, chat.owner)
        return chat


    def get_chat(self, uid: int) -> Optional[Chat]:
        self.cur.execute("SELECT * FROM chat WHERE uid = ?", (uid,))
        if (fetch := self.cur.fetchone()) is None:
            return None
        return Chat(*fetch)


    def get_chats(self, owner: int) -> List[Chat]:
        self.cur.execute("SELECT * FROM chat WHERE owner = ? ORDER BY last_accessed DESC", (owner,))
        return list(map(lambda c: Chat(*c), self.cur.fetchall()))

    
    def delete_chat(self, uid: int) -> None:
        if not self.chat_exists(uid):
            raise ValueError(f"Chat with uid {uid} does not exist")
        
        self.cur.execute("DELETE FROM chat WHERE uid = ?", (uid,)) \
                .execute("DELETE FROM message WHERE chat_id = ?", (uid,))
        self.con.commit()


    def create_message(self, message: str, author: str, chat_id: int) -> Message:
        self.cur.execute("INSERT INTO message (message, author, chat_id) VALUES (?, ?, ?)", (message, author, chat_id))
        uid = self.cur.lastrowid
        self.cur.execute("UPDATE chat SET last_accessed = CURRENT_TIMESTAMP WHERE uid = ?", (chat_id,))
        self.con.commit()
        return self.get_message(uid)


    def store_message(self, message: Message) -> Message:
        self.create_message(message.chat_id, message.message)
        return message


    def get_message(self, uid: int) -> Message:
        self.cur.execute("SELECT * FROM message WHERE uid = ?", (uid,))
        if (fetch := self.cur.fetchone()) is None:
            return None
        return Message(*fetch)


    def get_messages(self, chat_id: int) -> List[Message]:
        self.cur.execute("SELECT * FROM message WHERE chat_id = ? ORDER BY created_at ASC", (chat_id,))
        return list(map(lambda m: Message(*m), self.cur.fetchall()))
