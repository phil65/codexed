import os


# Before codexed is imported: strict models catch schema drift in test payloads.
os.environ["CODEXED_STRICT_MODELS"] = "1"
