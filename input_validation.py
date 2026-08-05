"""Reusable, testable validation helpers for the interactive client."""

def nonempty(value, label="value", max_length=128):
    value=value.strip()
    if not value: raise ValueError(f"{label} cannot be empty")
    if len(value)>max_length: raise ValueError(f"{label} is too long (maximum {max_length})")
    if any(ord(ch)<32 for ch in value): raise ValueError(f"{label} contains control characters")
    return value

def choice(value, choices, label="choice"):
    value=value.strip().lower()
    if value not in choices: raise ValueError(f"{label} must be one of: {', '.join(choices)}")
    return value

def csv_ids(value, label="IDs", allow_empty=True):
    if not value.strip():
        if allow_empty: return []
        raise ValueError(f"{label} cannot be empty")
    values=[nonempty(x,label) for x in value.split(",")]
    if len(values)!=len(set(values)): raise ValueError(f"{label} cannot contain duplicates")
    return values

def pairs(value, label="pairs"):
    if not value.strip(): return []
    result=[]
    for entry in value.split(","):
        if entry.count(":")!=1: raise ValueError(f"Each {label} entry must use left:right")
        left,right=(nonempty(x,label) for x in entry.split(":",1))
        result.append((left,right))
    if len({x[0] for x in result})!=len(result): raise ValueError(f"A left-side ID may appear only once in {label}")
    return result

def prompt_until(prompt, validator, input_fn=input, output_fn=print):
    while True:
        try: return validator(input_fn(prompt))
        except ValueError as exc: output_fn(f"Invalid input: {exc}")
