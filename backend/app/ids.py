import uuid

import uuid_utils


def uuid7() -> uuid.UUID:
    return uuid.UUID(str(uuid_utils.uuid7()))
