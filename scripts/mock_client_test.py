from app.mock_services import client

print(client.get_identity("00000-0000001-1")["full_name"])
print(client.get_identity("00000-9999999-9"))      # None means "not found"
print([p["full_name"] for p in client.search_identity("zainab")])
print(client.get_programme("00000-0000001-1"))