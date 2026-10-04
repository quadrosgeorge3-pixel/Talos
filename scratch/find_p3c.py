import os
import sys
for root, dirs, files in os.walk('models/TALOS-P3C'):
    for d in dirs:
        if 'gen099' in d or 'gen100' in d or '100' in d:
            print(os.path.join(root, d))
