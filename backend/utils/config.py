from pathlib import Path
import yaml

CONFIG_PATH = (
    Path(__file__).resolve().parents[1]#0当前目录 1所在文件夹上一级目录
    / "config"
    / "milvus.yaml"
)

with CONFIG_PATH.open("r",encoding="utf-8") as file:
    milvus_config = yaml.safe_load(file)