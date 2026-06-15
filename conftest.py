import os
import sys

# 确保项目根目录在 sys.path 上，使 `import orchestration` 在 pytest 下可用。
sys.path.insert(0, os.path.dirname(__file__))
