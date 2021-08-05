from Class.pipe import Pipe
import sys
print("Pipe Builder 3000")
config = "hosts.json"
if len(sys.argv) > 2:
    config = sys.argv[2]
pipe = Pipe(config)
if len(sys.argv) == 1:
    print("build, shutdown, clean, check, reboot")
elif sys.argv[1] == "build":
    pipe.run()
elif sys.argv[1] == "shutdown":
    pipe.shutdown()
elif sys.argv[1] == "clean":
    pipe.clean()
elif sys.argv[1] == "check":
    pipe.check()
elif sys.argv[1] == "reboot":
    pipe.reboot()
