from Class.pipe import Pipe
import sys
param = sys.argv[1]
print("Pipe Builder 3000")
pipe = Pipe()
if param == "build":
    pipe.run()
elif param == "shutdown":
    pipe.shutdown()
elif param == "clean":
    pipe.clean()
else:
    print("build, shutdown, clean")
