import functools
import pathlib
import time
from typing import Any, Callable, Optional

import peewee

from .utils import CACHING_DISABLED, USER_DATA_DIR, abspath


SCHEMA_VERSION = 1
DATABASE_PATH = pathlib.Path(USER_DATA_DIR).joinpath('data.db')
CACHE_EXPIRY_THRESHOLD = 3600 * 24 * 7  # A week

database = peewee.SqliteDatabase(None)
_database_initialized = False

AnyCallable = Callable[..., Any]


class _BaseModel(peewee.Model):
    class Meta:
        database = database


class URL(_BaseModel):
    url = peewee.TextField(unique=True)
    workdir = peewee.TextField()
    last_access = peewee.FloatField()  # POSIX timestamp


def initialize_database(path: pathlib.Path = None) -> None:
    global _database_initialized
    if _database_initialized:
        return

    if CACHING_DISABLED:
        _database_initialized = True
        return

    path = path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    database.init(path.as_posix())
    database.connect()

    schema_version = database.execute_sql('PRAGMA user_version;').fetchone()[0]
    if schema_version == 0:
        # New database
        database.execute_sql(f'PRAGMA user_version = {SCHEMA_VERSION};')

    database.create_tables([URL], safe=True)

    # Expire old entries
    expiry_time = time.time() - CACHE_EXPIRY_THRESHOLD
    URL.delete().where(URL.last_access < expiry_time).execute()

    _database_initialized = True


# Decorator to ensure database is initialized before executing a
# function.
def ensure_database(func: AnyCallable) -> AnyCallable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        initialize_database()
        return func(*args, **kwargs)
    return wrapper


# Decorator that's basically equivalent to database.atomic().
def atomic(func: AnyCallable) -> AnyCallable:
    if CACHING_DISABLED:
        return func
    else:
        return ensure_database(database.atomic()(func))


# Returns a decorator that returns the fallback value if caching is
# disabled.
def requires_cache(fallback: Any = None) -> Callable[[AnyCallable], AnyCallable]:
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if CACHING_DISABLED:
                return fallback
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator


@requires_cache()
@ensure_database
@database.atomic()
def insert(url: str, workdir: pathlib.Path) -> None:
    workdir_str = abspath(workdir).as_posix()
    try:
        record = URL.get(URL.url == url)
        record.workdir = workdir_str
        record.last_access = time.time()
        record.save()
    except peewee.DoesNotExist:
        URL.create(url=url, workdir=workdir_str, last_access=time.time())


@requires_cache()
@ensure_database
@database.atomic()
def touch(url: str) -> None:
    try:
        record = URL.get(URL.url == url)
        record.last_access = time.time()
        record.save()
    except peewee.DoesNotExist:
        pass


@requires_cache()
@ensure_database
@database.atomic()
def drop(url: str) -> None:
    try:
        record = URL.get(URL.url == url)
        record.delete_instance()
    except peewee.DoesNotExist:
        pass


@requires_cache()
@ensure_database
def get_workdir(url: str) -> Optional[pathlib.Path]:
    try:
        record = URL.get(URL.url == url)
        return pathlib.Path(record.workdir)
    except peewee.DoesNotExist:
        return None
