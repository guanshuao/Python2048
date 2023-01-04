# 导入相关库
import pygame
import os
import time

from pygame.locals import *
from game import Game
from ai import Ai
from config import *

# 选择速度，有Fast，Slow可供选择
config = Fast()
# config = Slow()

FPS = config.FPS  # 帧率
SIZE = config.SIZE  # 棋盘大小
DEBUG = config.DEBUG  # 是否显示调试信息
COLOR = config.COLORS  # 颜色设置
GAME_WH = config.GAME_WH  # 游戏区域的宽度
WINDOW_W = config.WINDOW_WIDTH  # 窗口宽度
WINDOW_H = config.WINDOW_HEIGHT  # 窗口高度

# 格子中的字体
font_h_w = 2 / 1  # 字体高宽比
g_w = GAME_WH / SIZE * 0.9  # 格子宽度

'''初始化一个游戏的主类，准备开始运行游戏。

这段代码是一个 Python 程序的主函数，它定义了一个名为 Main 的类。在这个类中，定义了一个名为 init 的特殊方法，这个方法会在创建 Main 类的实例时被调用。

在这个方法中，首先调用了 pygame 库的初始化函数，然后设置了窗口的标题和大小，设置了游戏的帧率，创建了一个游戏的实例，创建了一个 AI 类的实例。

在这个方法中还有一些其他的变量，比如 self.state、self.catch_n 和 self.step_time 等，这些变量在程序的其他地方也会被使用。'''


class Main():
    def __init__(self):
        global FPS
        pygame.init()
        os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (100, 50)  # 设置窗口位置
        self.set_win_wh(WINDOW_W, WINDOW_H, title='2048')  # 设置窗口大小和标题
        self.state = 'start'
        self.fps = FPS
        self.catch_n = 0
        self.clock = pygame.time.Clock()  # 创建一个Clock对象
        self.game = Game(SIZE)  # 创建游戏对象
        self.ai = Ai()  # 创建AI对象
        self.step_time = config.STEP_TIME  # 每步的时间间隔
        self.next_f = ''
        self.hint_next_f = ''  # 下一步的提示信息
        self.hint_update = True  # 是否更新提示信息的标志
        self.hint_text = ''  # 提示信息文本
        self.last_time = time.time()  # 上一步的时间
        self.jm = -1  # 用于记录上一步的方向

        self.hint_mode = False  # 添加一个提示模式的变量，初始值为 False

    def start(self):
        # 加载按钮，分为两种状态
        self.button_list = \
            [
                Button('start', 'Restart', (GAME_WH + 50, 150)),  # 重新开始
                Button('ai', 'Auto Off', (GAME_WH + 50, 250)),  # 电脑托管模式
                Button('hint', 'Hint Off', (GAME_WH + 50, 350)),  # 提示模式
            ]
        self.run()

    def run(self):
        while self.state != 'exit':
            if self.game.state in ['over', 'win']:
                self.state = self.game.state
            self.my_event()
            if self.next_f != '' and (
                    self.state == 'run' or self.state == 'ai' and time.time() - self.last_time > self.step_time):
                self.game.run(self.next_f)
                self.next_f = ''
                self.last_time = time.time()
            elif self.state == 'start':
                self.game.start()
                self.state = 'run'
            self.set_bg((255, 255, 255))
            self.draw_info()
            self.draw_button(self.button_list)
            self.draw_map()
            self.update()
        print('Exit')

    def draw_map(self):  # 画出棋盘
        '''使用两层循环来遍历棋盘上的每一个格子，并调用"draw_block"函数来绘制每个格子'''
        for y in range(SIZE):
            for x in range(SIZE):
                self.draw_block((x, y), self.game.grid.tiles[y][x])
        '''检查当前的游戏状态，如果游戏已经结束（即 "state" 变量为 "over" 或 "win"），则绘制一个半透明的黑色矩形，并调用一个名为 "draw_text" 的函数来在棋盘上绘制文本。文本内容根据当前的游戏状态而定，如果游戏已经结束则显示 "Game Over!"，如果游戏胜利则显示 "Victory!"。'''
        if self.state == 'over':
            pygame.draw.rect(self.screen, (0, 0, 0, 0.5),
                             (0, 0, GAME_WH, GAME_WH))
            self.draw_text('Game Over!', (GAME_WH / 2, GAME_WH / 2), size=25, center='center')

        elif self.state == 'win':
            pygame.draw.rect(self.screen, (0, 0, 0, 0.5),
                             (0, 0, GAME_WH, GAME_WH))
            self.draw_text('Victory!', (GAME_WH / 2, GAME_WH / 2), size=25, center='center')

    # 在屏幕上绘制棋盘上的一个方块
    ''''''

    def draw_block(self, xy, number):
        '''xy 是一个元组，表示方块的位置，number 是一个整数，表示方块上的数字。'''
        '''函数计算出每个方块的大小，并使用 Pygame 库绘制一个矩形。矩形的颜色由 "number" 参数决定，如果 "number" 小于等于 2048 则使用 "COLOR" 字典中的值，否则使用蓝色。'''
        one_size = GAME_WH / SIZE
        dx = one_size * 0.05
        x, y = xy[0] * one_size, xy[1] * one_size
        color = COLOR[str(int(number))] if number <= 2048 else (0, 0, 255)
        pygame.draw.rect(self.screen, color,
                         (x + dx, y + dx, one_size - 2 * dx, one_size - 2 * dx))
        color = (20, 20, 20) if number <= 4 else (250, 250, 250)
        '''如果方块上的数字不为 0，则调用 "draw_text" 函数在方块中间绘制数字。'''
        if number != 0:
            ln = len(str(number))
            if ln == 1:
                size = one_size * 1.2 / 2
            elif ln <= 3:
                size = one_size * 1.2 / ln
            else:
                size = one_size * 1.5 / ln

            self.draw_text(str(int(number)), (x + one_size * 0.5, y + one_size * 0.5 - size / 2), color, size, 'center')

    # 显示得分
    def draw_info(self):
        self.draw_text('Scores：{}'.format(self.game.score), (GAME_WH + 50, 40))
        if self.hint_mode:
            if self.hint_text == 'D':
                self.hint_text = 'Down'
            if self.hint_text == 'L':
                self.hint_text = 'Left'
            if self.hint_text == 'R':
                self.hint_text = 'Right'
            if self.hint_text == 'U':
                self.hint_text = 'Up'
            self.draw_text('Next step:{}'.format(self.hint_text), (GAME_WH + 50, 100))

    '''设置背景颜色白色'''

    def set_bg(self, color=(255, 255, 255)):
        self.screen.fill(color)

    def catch(self, filename=None):
        if filename is None:
            filename = "./catch/catch-{:04d}.png".format(self.catch_n)
        pygame.image.save(self.screen, filename)
        self.catch_n += 1

    def draw_button(self, buttons):
        for b in buttons:
            if b.is_show:
                pygame.draw.rect(self.screen, (180, 180, 200),
                                 (b.x, b.y, b.w, b.h))
                self.draw_text(b.text, (b.x + b.w / 2, b.y + 9), size=18, center='center')

    def draw_text(self, text, xy, color=(0, 0, 0), size=18, center=None):
        font = pygame.font.SysFont('microsoftyahei', round(size))
        text_obj = font.render(text, 1, color)
        text_rect = text_obj.get_rect()
        if center == 'center':
            text_rect.move_ip(xy[0] - text_rect.w // 2, xy[1])
        else:
            text_rect.move_ip(xy[0], xy[1])
        # print('画文字：',text,text_rect)
        self.screen.blit(text_obj, text_rect)

    # 设置窗口大小
    def set_win_wh(self, w, h, title='Python2048'):
        self.screen2 = pygame.display.set_mode((w, h), pygame.DOUBLEBUF, 32)
        self.screen = self.screen2.convert_alpha()
        pygame.display.set_caption(title)

    def update(self):
        self.screen2.blit(self.screen, (0, 0))
        pygame.display.flip()
        time_passed = self.clock.tick(self.fps)

    # 侦听事件
    def my_event(self):
        if self.state == 'ai' and self.next_f == '':
            self.next_f, self.jm = self.ai.get_next(self.game.grid.tiles)
            print(self.next_f)
        if self.hint_mode and self.next_f == '':
            self.hint_next_f, self.jm = self.ai.get_next(self.game.grid.tiles)
            if self.hint_update:
                self.hint_text = self.hint_next_f
                self.hint_update = False
        for event in pygame.event.get():
            if event.type == QUIT:
                self.state = 'exit'
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.state = 'exit'
                elif event.key in [K_LEFT, K_a] and self.state == 'run':
                    self.next_f = 'L'
                    self.hint_update = True
                elif event.key in [K_RIGHT, K_d] and self.state == 'run':
                    self.next_f = 'R'
                    self.hint_update = True
                elif event.key in [K_DOWN, K_s] and self.state == 'run':
                    self.next_f = 'D'
                    self.hint_update = True
                elif event.key in [K_UP, K_w] and self.state == 'run':
                    self.next_f = 'U'
                    self.hint_update = True
                elif event.key in [K_k, K_l] and self.state == 'ai':
                    if event.key == K_k and self.step_time > 0:
                        self.step_time *= 0.9
                    if event.key == K_l and self.step_time < 10:
                        if self.step_time != 0:
                            self.step_time *= 1.1
                        else:
                            self.step_time = 0.01
                    if self.step_time < 0:
                        self.step_time = 0

            if event.type == MOUSEBUTTONDOWN:
                for i in self.button_list:
                    if i.is_click(event.pos):
                        self.state = i.name
                        if i.name == 'ai':
                            i.name = 'run'
                            i.text = 'Auto On'
                        elif i.name == 'run':
                            i.name = 'ai'
                            i.text = 'Auto Off'
                        elif i.name == 'hint':
                            i.name = 'hintOn'
                            i.text = 'Hint On'
                            self.state = 'run'
                            self.hint_mode = True
                        elif i.name == 'hint On':
                            i.name = 'hint'
                            i.text = 'Hint Off'
                            self.state = 'run'
                            self.hint_mode = False
                        break


# 定义按钮类
class Button(pygame.sprite.Sprite):
    def __init__(self, name, text, xy, size=(100, 50)):
        pygame.sprite.Sprite.__init__(self)
        self.name = name
        self.text = text
        self.x, self.y = xy[0], xy[1]
        self.w, self.h = size
        self.is_show = True

    # 判断是否点击按钮
    def is_click(self, xy):
        return (self.is_show and
                self.x <= xy[0] <= self.x + self.w and
                self.y <= xy[1] <= self.y + self.h)


if __name__ == '__main__':
    Main().start()
