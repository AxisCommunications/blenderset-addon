def get_all_tags(collection):
    tags = set()
    for entry in collection.values():
        for tag in entry["tags"]:
            tags.add(tag)
    return tags


def filter_by_tags(collection, tags):
    if tags is None:
        return collection
    if isinstance(tags, str):
        tags = [tags]
    filtered = {}
    for name, entry in collection.items():
        for t in tags:
            if t[0] == "~":
                if t[1:] in entry["tags"]:
                    break
            elif t not in entry["tags"]:
                break
        else:
            filtered[name] = entry
    return filtered
