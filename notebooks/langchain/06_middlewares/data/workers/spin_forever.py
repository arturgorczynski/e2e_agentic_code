"""A deliberate CPU loop. Run ONLY through the bounded sandbox helpers."""
print("Worker is computing forever.", flush=True)
counter = 0
while True:
    counter += 1
