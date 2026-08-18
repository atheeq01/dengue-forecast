from pathlib import Path
import pandas as pd

def save_parquet(df: pd.DataFrame,path:Path)->None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path,index=False)

    print(f"[saved] {path}")
    print(f"        rows={len(df):,}")
    print(f"        columns={len(df.columns):,}")

def load_parquest(path:Path)->pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError( f"Required parquet file does not exist: {path}")
    return pd.read_parquet(path)