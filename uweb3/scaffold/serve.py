"""Starts a simple application development server."""

# Application
import base
import socketio
from uweb3.sockets import Uweb3SocketIO

def websocket_routes(sio):
  @sio.on("connect")
  def test(sid, env):
    print("WEBSOCKET ROUTE CALLED: ", sid, env)

def main():
  sio = socketio.Server()
  # websocket_routes(sio)
  return sio

if __name__ == '__main__':
  sio = main()
  Uweb3SocketIO(base.main(sio), sio)


# # Application
# import base

# def main():
#   app = base.main()
#   app.serve()

# if __name__ == '__main__':
#   main()