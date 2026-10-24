"""A deliberately stuck worker. Run ONLY through the bounded sandbox helpers."""
import time

print("Worker is waiting forever.", flush=True)
while True:
    time.sleep(1)
