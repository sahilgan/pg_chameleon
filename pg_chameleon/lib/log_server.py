import os
import sys
import select
import pickle
import logging
import struct
import argparse
from daemonize import Daemonize
import socketserver
import logging.config
import logging.handlers
import traceback

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = logging.handlers.DEFAULT_TCP_LOGGING_PORT
PID_DIR = '.hedgelog'


class LogHandler(socketserver.StreamRequestHandler):
    def handle(self):
        """Deal with the incoming log data"""
        while True:
            chunk = self.connection.recv(4)
            if len(chunk) < 4:
                break
            struct_len = struct.unpack('>L', chunk)[0]
            chunk = self.connection.recv(struct_len)
            while len(chunk) < struct_len:
                chunk = chunk + self.connection.recv(struct_len - len(chunk))
            obj = self.unpickle(chunk)
            record = logging.makeLogRecord(obj)
            self.handle_log_record(record)

    @staticmethod
    def unpickle(data):
        return pickle.loads(data)

    def handle_log_record(self, record):
        # name = self.server.logname if self.server.logname is not None else record.name
        name = record.name
        logging.getLogger(name).handle(record)


class LogReceiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, handler=LogHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        abort = 0
        while not abort:
            read_items, _, _ = select.select([self.socket.fileno()], [], [], self.timeout)
            if read_items:
                self.handle_request()
            abort = self.abort


def init_logging(dict_path):
    import json
    with open(dict_path, 'r') as f:
        conf = json.load(f)
    logging.config.dictConfig(conf)

    fd_to_search = conf['loggers'].keys()
    fds = []
    for k, val in logging.Logger.manager.loggerDict.items():
        if k in fd_to_search and val.hasHandlers():
            fds.extend([fd.stream.fileno() for fd in val.handlers])
    return fds


class HedgeLog:
    def __init__(self, address, port, log_c_path):
        self.pid_folder = os.path.expanduser('~/%s' % PID_DIR)
        if not os.path.exists(self.pid_folder):
            os.mkdir(self.pid_folder, 0o751)
        self.pid_path = os.path.expanduser('~/%s/%s.pid' % (PID_DIR, 'hedgelog'))
        self.address = address
        self.port = port
        self.log_dict_path = log_c_path

    def ignite_server(self):
        tcpserver = LogReceiver(host=self.address, port=int(self.port))
        print("Starting TCP server -  %s:%s" % (self.address, self.port))
        tcpserver.serve_until_stopped()

    def start_server(self, debug=False):
        keep_fds = init_logging(self.log_dict_path)
        if debug:
            self.ignite_server()
        else:
            print(self.pid_path)
            log_daemon = Daemonize(app='HedgeLog', pid=self.pid_path, action=self.ignite_server,
                                   keep_fds=keep_fds,
                                   foreground=False)
            try:
                log_daemon.start()
                print("HedgeLog started...")
            except:
                print("HedgeLog is already started OR port %d is occupied // %s" % (self.port, self.pid_path))

    def stop_server(self):
        if os.path.isfile(self.pid_path):
            try:
                file_pid = open(self.pid_path, 'r')
                pid = file_pid.read()
                file_pid.close()
                os.kill(int(pid), 2)
                print("Trying to shutdown HedgeLog")
                while True:
                    try:
                        os.kill(int(pid), 0)
                    except:
                        break
                print("HedgeLog finished his dirty work!")
            except:
                print("HedgeLog pissed off! Try to kill him manually")
        else:
            print("No PID file found at \'%s\', trying to kill deadman?" % self.pid_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Command line for HedgeLog:', add_help=True)
    parser.add_argument('command', type=str, help='start/stop')
    parser.add_argument('--config', type=str, help='JSON configuration for logging')
    parser.add_argument('--host', type=str, help='Bind address')
    parser.add_argument('--port', type=str, help='Bind port')
    parser.add_argument('--debug', default=False, required=False, action='store_true')
    args = parser.parse_args()

    h = HedgeLog(args.host, args.port, args.config)

    if args.command == 'start':
        h.start_server(args.debug)
    elif args.command == 'stop':
        h.stop_server()
    else:
        print("Don't know what to do.")


