"""Deleting a brand, category or unit still in use: what uses it moves to
another first (moveTo), then it's deleted. Without somewhere to go, it isn't."""

from tests.conftest import Api  # noqa: F401 (the type of the fixtures)


def delete(api, path, move_to=None):
    return api.c.delete(path, headers=api.h, params={"moveTo": move_to} if move_to else None)


def test_a_brand_in_use_moves_its_products_first(ana, world):
    old = ana.post("/inventory/brands", {"name": "2MG"})["id"]
    new = ana.post("/inventory/brands", {"name": "Getmeds"})["id"]
    for p in (world["gloves"], world["pcm"]):
        ana.patch(f"/inventory/products/{p}", {"brandId": old})

    r = delete(ana, f"/inventory/brands/{old}")
    assert r.status_code == 409 and "Pick a brand to move them to" in r.text
    assert delete(ana, f"/inventory/brands/{old}", old).status_code == 422  # not onto itself

    assert delete(ana, f"/inventory/brands/{old}", new).status_code == 204
    brands = {b["name"]: b["productCount"] for b in ana.get("/inventory/brands")}
    assert brands == {"Getmeds": 2}
    assert ana.get(f"/inventory/products/{world['gloves']}")["brand"]["name"] == "Getmeds"


def test_a_category_moves_its_products_and_the_categories_inside_it(ana, world):
    supplies = ana.post("/inventory/categories", {"name": "Supplies"})["id"]
    gloves = ana.post("/inventory/categories", {"name": "Gloves", "parentId": supplies})["id"]
    medical = ana.post("/inventory/categories", {"name": "Medical"})["id"]
    ana.patch(f"/inventory/products/{world['gloves']}", {"categoryId": supplies})

    assert delete(ana, f"/inventory/categories/{supplies}").status_code == 409
    r = delete(ana, f"/inventory/categories/{supplies}", gloves)
    assert r.status_code == 422 and "inside this one" in r.text  # not into its own

    assert delete(ana, f"/inventory/categories/{supplies}", medical).status_code == 204
    cats = {c["name"]: c for c in ana.get("/inventory/categories")}
    assert set(cats) == {"Gloves", "Medical"}
    assert cats["Gloves"]["parentId"] == medical
    assert cats["Medical"]["productCount"] == 1


def test_a_unit_moves_its_products_and_nothing_unused_needs_a_target(ana, world):
    ana.post("/inventory/units", {"code": "bx", "name": "Box (old)"})
    ana.patch(f"/inventory/products/{world['gloves']}", {"unitCode": "bx"})
    assert delete(ana, "/inventory/units/bx").status_code == 409
    assert delete(ana, "/inventory/units/bx", "box").status_code == 204
    assert ana.get(f"/inventory/products/{world['gloves']}")["unit"] == "box"

    spare = ana.post("/inventory/brands", {"name": "Unused"})["id"]
    assert delete(ana, f"/inventory/brands/{spare}").status_code == 204
