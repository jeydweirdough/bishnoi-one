from app.config import Settings
from app.store.local import LocalBackend
from app.store.records import Records
from app.store.sanity import SanityBackend


def build_records(settings: Settings) -> Records:
    if settings.uses_sanity:
        return Records(
            SanityBackend(
                settings.sanity_project_id,
                settings.sanity_dataset,
                settings.sanity_token,
                settings.sanity_api_version,
            )
        )
    return Records(LocalBackend(settings.local_store_path))
