#! /usr/bin/env python2.7
import sys
import signal
import futures

import config
import parser
import err
from functions import *

def run(socket, channels, cmds, auto_cmds, nick, logfile):
    # buffer for some command received
    buff = ''

    #TODO: sometimes I don't get a reply anymore, I think because of !channels
    #being issued two times in a row too fast - this means that it's not a good
    #idea to give access to socket to a command since it can block it
    #TODO: what happens if I use all the workers?
    #TODO: check what happens on exceptions and when the commands do
    #something that might kill the bot
    #TODO: as I use send_response noew from the callback I should lock it so I
    #don't use the socket from two threads at the same time(this could happen if
    #two cmds finish working at the same time too), same goes for log_write
    # in other words it should be made threadsafe
    #nothing happens after I issue !channels to the bot

    #I cannot send socket to a ProcessPoolExecutor since it isn't
    #pickable, so for now I'm stuck with ThreadPoolExecutor
    with futures.ThreadPoolExecutor(max_workers=len(cmds) + len(auto_cmds)) as executor:
        while len(channels):
            receive = socket.recv(4096)
            buff = buff + receive
            response = ''

            if receive:
                log_write(logfile, get_datetime()['time'], ' <> ', receive + \
                    ('' if '\n' == receive[len(receive)-1] else '\n'))

            if -1 != buff.find('\n'):
                # get a full command from the buffer
                command = buff[0 : buff.find('\n')]
                buff = buff[buff.find('\n')+1 : ]

                # command's components after parsing
                components = parser.parse_command(command)
                to = send_to(command)

                if 'PING' == components['action']:
                    response = []
                    response.append('PONG')
                    response.append(':' + components['arguments'])

                elif 'PRIVMSG' == components['action']:
                    if '!' == components['arguments'][0]:
                        # a command from a user only makes sense if it starts
                        # with an exclamation mark

                        pos = components['arguments'].find(' ')
                        if -1 == pos:
                            pos = len(components['arguments'])

                        # get the command issued to the bot without the "!"
                        cmd = components['arguments'][1:pos]
                        callable_cmd = get_cmd(cmd, cmds)
                        if callable_cmd:
                            run_cmd(socket, executor, to, callable_cmd,
                                    components)

                    # run auto commands
                    for cmd in config.auto_cmds_list:
                        callable_cmd = get_cmd(cmd, auto_cmds)
                        if callable_cmd:
                            run_cmd(socket, executor, to, callable_cmd,
                                    components)

                elif 'KICK' == components['action'] and \
                    nick == components['action_args'][1]:
                        channels.remove(components['action_args'][0])

                elif 'QUIT' == components['action'] and \
                        -1 != components['arguments'].find('Ping timeout: '):
                    channels[:] = []

                # this call is still necessary in case that a PONG response
                # should be sent altough every other response is sent when the
                # futures finish working
                send_response(response, to, socket, logfile)

                buff = ''


def main():
    valid_cfg = check_cfg(config.owner, config.server, config.nicks,
            config.real_name, config.log, config.cmds_list)

    if not valid_cfg:
        sys.exit(err.INVALID_CFG)

    if not check_channel(config.channels):
        sys.exit(err.INVALID_CHANNELS)

    signal.signal(signal.SIGINT, sigint_handler)

    logfile = config.log + get_datetime()['date'] + '.log'

    socket = create_socket(logfile)

    if socket and connect_to((config.server, config.port), socket, logfile):
        content = 'Connected to {0}:{1}'.format(config.server, config.port)
        log_write(logfile, get_datetime()['time'], ' <> ', content + '\n')
        print content

        config.current_nick = name_bot(socket, config.nicks, config.real_name,
            logfile)
        joined = join_channels(config.channels, socket, logfile)

        if joined:
            run(socket, config.channels, config.cmds_list,
                    config.auto_cmds_list, config.current_nick, logfile)

        quit_bot(socket, logfile)
        socket.close()

        content = 'Disconnected from {0}:{1}'.format(
            config.server, config.port)
        log_write(logfile, get_datetime()['time'], ' <> ', content + '\n')
        print content

if __name__ == '__main__': #pragma: no cover
    main()
