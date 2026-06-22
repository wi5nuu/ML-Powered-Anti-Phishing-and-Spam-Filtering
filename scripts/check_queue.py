import redis
r = redis.Redis(host="localhost", port=6379)
qsize = r.llen("email_pipeline")
print(f"Queue size: {qsize}")
if qsize > 0:
    item = r.lindex("email_pipeline", 0)
    print(f"First item preview: {item[:200] if item else 'None'}")
