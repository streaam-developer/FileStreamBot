import pymongo
import time
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from FileStream.config import Telegram, Server
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
import motor.motor_asyncio
from bson.objectid import ObjectId
from bson.errors import InvalidId
from FileStream.server.exceptions import FIleNotFound

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.black = self.db.blacklist
        self.file = self.db.file

#---------------------[ NEW USER ]---------------------#
    def new_user(self, id):
        return dict(
            id=id,
            join_date=time.time(),
            Links=0
        )

# ---------------------[ ADD USER ]---------------------#
    async def add_user(self, id):
        user = self.new_user(id)
        await self.col.insert_one(user)

# ---------------------[ GET USER ]---------------------#
    async def get_user(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user

# ---------------------[ CHECK USER ]---------------------#
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

# ---------------------[ REMOVE USER ]---------------------#
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

# ---------------------[ BAN, UNBAN USER ]---------------------#
    def black_user(self, id):
        return dict(
            id=id,
            ban_date=time.time()
        )

    async def ban_user(self, id):
        user = self.black_user(id)
        await self.black.insert_one(user)

    async def unban_user(self, id):
        await self.black.delete_one({'id': int(id)})

    async def is_user_banned(self, id):
        user = await self.black.find_one({'id': int(id)})
        return True if user else False

    async def total_banned_users_count(self):
        count = await self.black.count_documents({})
        return count
        
# ---------------------[ ADD FILE TO DB ]---------------------#
    async def add_file(self, file_info):
        file_info["time"] = time.time()
        fetch_old = await self.get_file_by_fileuniqueid(file_info["user_id"], file_info["file_unique_id"])
        if fetch_old:
            return fetch_old["_id"]
        await self.count_links(file_info["user_id"], "+")
        return (await self.file.insert_one(file_info)).inserted_id

# ---------------------[ FIND FILE IN DB ]---------------------#
    async def find_files(self, user_id, range):
        user_files=self.file.find({"user_id": user_id})
        user_files.skip(range[0] - 1)
        user_files.limit(range[1] - range[0] + 1)
        user_files.sort('_id', pymongo.DESCENDING)
        total_files = await self.file.count_documents({"user_id": user_id})
        return user_files, total_files

    async def get_file(self, _id):
        try:
            file_info=await self.file.find_one({"_id": ObjectId(_id)})
            if not file_info:
                raise FIleNotFound
            return file_info
        except InvalidId:
            raise FIleNotFound
    
    async def get_file_by_fileuniqueid(self, id, file_unique_id, many=False):
        if many:
            return self.file.find({"file_unique_id": file_unique_id})
        else:
            file_info=await self.file.find_one({"user_id": id, "file_unique_id": file_unique_id})
        if file_info:
            return file_info
        return False

# ---------------------[ TOTAL FILES ]---------------------#
    async def total_files(self, id=None):
        if id:
            return await self.file.count_documents({"user_id": id})
        return await self.file.count_documents({})

# ---------------------[ DELETE FILES ]---------------------#
    async def delete_one_file(self, _id):
        await self.file.delete_one({'_id': ObjectId(_id)})

# ---------------------[ UPDATE FILES ]---------------------#
    async def update_file_ids(self, _id, file_ids: dict):
        await self.file.update_one({"_id": ObjectId(_id)}, {"$set": {"file_ids": file_ids}})

# ---------------------[ PAID SYS ]---------------------#
#     async def link_available(self, id):
#         user = await self.col.find_one({"id": id})
#         if user.get("Plan") == "Plus":
#             return "Plus"
#         elif user.get("Plan") == "Free":
#             files = await self.file.count_documents({"user_id": id})
#             if files < 11:
#                 return True
#             return False
        
    async def count_links(self, id, operation: str):
        if operation == "-":
            await self.col.update_one({"id": id}, {"$inc": {"Links": -1}})
        elif operation == "+":
            await self.col.update_one({"id": id}, {"$inc": {"Links": 1}})


##############################################################################
Telegram.DATABASE_URI, Telegram.DATABASE_NAME, COLLECTION_NAME = Telegram.DATABASE_URI, Telegram.DATABASE_NAME, Telegram.COLLECTION_NAME

client = AsyncIOMotorClient(Telegram.DATABASE_URI)
db = client[Telegram.DATABASE_NAME]
instance = Instance(db)


@instance.register
class Data(Document):
    id = fields.StrField(attribute='_id')
    channel = fields.StrField()
    file_type = fields.StrField()
    message_id = fields.IntField()
    use = fields.StrField()
    methord = fields.StrField()
    caption = fields.StrField()

    class Meta:
        collection_name = COLLECTION_NAME

async def save_data(id, channel, message_id, methord, caption, file_type):
    try:
        data = Data(
            id=id,
            use = "forward",
            channel=channel,
            message_id=message_id,
            methord=methord,
            caption=caption,
            file_type=file_type
        )
    except ValidationError:
        print('Error occurred while saving file in database')
    try:
        await data.commit()
    except DuplicateKeyError:
        print("Already saved in Database")
    else:
        try:
            print("Messsage saved in DB")
        except:
            pass

async def get_search_results():
    filter = {'use': "forward"}
    cursor = Data.find(filter)
    cursor.sort('$natural', -1)
    cursor.skip(0).limit(1)
    Messages = await cursor.to_list(length=1)
    return Messages
