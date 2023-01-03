class Base:
    WINDOW_WIDTH = 700 # 窗口宽度
    WINDOW_HEIGHT = 550 #窗口高度
    GAME_WH = 500 # 游戏区域的宽高
    #从用户输入获取游戏阶数
    SIZE = eval(input("Welcome to 2048 Mini Game! \n"
                      "欢迎来到2048小游戏!\n"
                      "The developers of this program are Guanshu AO, Zhonglei TANG, Junsong WANG and Yifan WANG \n"
                      "本游戏的开发者为敖冠舒、唐中磊、王骏松、王一帆\n"
                      "Please enter an integer not less than 3 as the number of orders for the game: \n"
                      "请输入一个不小于3的整数，作为方格的阶数："))
    FPS = 60
    DEBUG = True
    COLORS = {
        '0': (205, 193, 180),# 0为空白砖块
        '2': (238, 228, 218),
        '4': (237, 224, 200),
        '8': (242, 177, 121),
        '16': (245, 149, 99),
        '32': (246, 124, 95),
        '64': (246, 94, 59),
        '128': (237, 207, 114),
        '256': (237, 204, 97),
        '512': (237, 200, 80),
        '1024': (237, 197, 63),
        '2048': (255, 0, 0)
    }

class Fast(Base):
    STEP_TIME = 0
    ANIMATION = True

class Slow(Base):
    STEP_TIME = 0.3
    ANIMATION = True

