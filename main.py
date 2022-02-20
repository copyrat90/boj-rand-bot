import sys
import logging

import brb_commands
try:
    import brb_custom_commands
except:
    pass

if __name__ == '__main__':
    try:
        token_file = open('token.txt', 'r')
    except:
        logging.error('token.txt 파일을 열 수 없습니다.')
        sys.exit()

    token = token_file.readline().rstrip()
    token_file.close()

    if not token:
        logging.error('token.txt 파일이 비었습니다.')
        sys.exit()

    logging.basicConfig(level=logging.INFO)

    brb_commands.bot.run(token)
