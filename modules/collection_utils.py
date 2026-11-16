def compare_local_encora_ids(local_ids: list, encora_data: list) -> tuple[list[str], list[str]]:
    """Compare local Encora IDs with the fetched Encora collection."""
    encora_collection_ids = {
        str(item['recording']['id']).strip()
        for item in encora_data
        if 'recording' in item and 'id' in item['recording']
    }

    normalized_local_ids = []
    for item in local_ids:
        if isinstance(item, tuple):
            normalized_local_ids.append(str(item[0]).strip())
        elif isinstance(item, str):
            normalized_local_ids.append(item.strip().strip('{}').replace('e-', ''))

    local_set = set(normalized_local_ids)
    missing_ids = [eid for eid in encora_collection_ids if eid not in local_set]
    extra_ids = [eid for eid in normalized_local_ids if eid not in encora_collection_ids]
    return missing_ids, extra_ids
