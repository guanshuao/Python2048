import itertools
import numpy as np
from game import Grid, Game
from config import *

'''这段代码定义了一个类 Ai，这个类用于解决2048游戏问题。它包含了一些方法，如 get_next()、get_score() 和 debug() 等。

其中，get_next() 方法用于获取下一步的最优移动方向，并通过使用 itertools 库的 product() 方法生成所有可能的移动序列，然后对于每个序列都调用 get_grid() 方法和 get_score() 方法来计算分数，最后将所有序列的分数进行排序，选取分数最高的序列的第一个方向作为最优移动方向。

get_score() 方法用于获取当前棋盘的分数，它通过调用 get_bj2__4() 和 get_bj__4() 方法计算金角银边的得分并相加得出最终分数。

debug() 方法用于调试，它与 get_next() 方法类似，但会打印出每一步的棋盘状态和当前的分数。'''

config = Fast()

'''get_grid() 函数接受两个参数：tiles 和 directions。

tiles 参数表示当前棋盘的状态，是一个二维数组，存储了每个格子的值。

directions 参数表示要进行的移动方向序列，是一个字符串的列表，其中每个字符表示一个方向，"U" 表示向上移动，"D" 表示向下移动，"L" 表示向左移动，"R" 表示向右移动。

函数的作用是模拟移动棋盘，首先它会创建一个 Grid 类的实例，然后把当前的棋盘状态复制给这个实例的 tiles 属性，然后按照 directions 参数中的顺序对棋盘进行移动，每次移动后调用 add_random_tile() 方法在棋盘上随机添加一个新的格子。最后返回棋盘的状态。

例如，调用 get_grid([[2, 4, 8, 16], [32, 64, 128, 256], [512, 1024, 2048, 4096], [8192, 16384, 32768, 65536]], ["U", "L", "D", "R"]) 将会模拟向上、左、下、右四个方向依次移动，并在每次移动后随机添加一个新的格子，最终返回移动后的棋盘状态'''

def get_grid(tiles, directions):
    g = Grid(config.SIZE)
    g.tiles = tiles.copy()
    for direction in directions:
        g.run(direction)
        g.add_random_tile()
    return g.tiles

'''printf() 函数接受一个参数 tiles，表示棋盘的状态。

函数的作用是在控制台输出棋盘的状态，它通过两层循环遍历每个格子的值，并使用字符串的 format() 方法将值输出为字符串，最后使用 print() 函数输出到控制台。

例如，调用 printf([[2, 4, 8, 16], [32, 64, 128, 256], [512, 1024, 2048, 4096], [8192, 16384, 32768, 65536]]) 将会在控制台输出如下内容：

  2    4    8   16
 32   64  128  256
512 1024 2048 4096
8192 16384 32768 65536
'''
def printf(tiles):
    for row in tiles:
        for i in row:
            print("{:^6}".format(i), end='')
        print()


def H(z):
    if z == 0:
        return 0
    else:
        return z

'''这段代码定义了 Ai 类，并在类中定义了两个方法：

__init__() 方法是类的构造函数，它在创建类的实例时自动调用。这个方法主要是创建一个 Grid 类的实例，并将其赋值给类的 g 属性。

get_next() 方法用于获取下一步的最优移动方向。它接受一个参数 tiles，表示当前棋盘的状态。首先调用 get_num() 方法计算当前棋盘上有多少个格子是已经有数字的，如果超过棋盘的一半就随机返回 "U" 或 "D" 两个方向之一。'''

'''gen_next首先会计算出一个数值 kn，它是当前棋盘的已有数字数量的平方与 20 之间的最小值，但是不能超过 40。

然后使用 itertools 库的 product() 方法生成所有可能的移动序列，对于每个序列都调用 get_grid() 方法和 get_score() 方法来计算分数，并将结果存储在一个列表中。

接着将所有序列的分数按照从小到大的顺序排序，然后从最高分的序列开始遍历，如果能够找到一个序列的第一个方向能够使得棋盘发生变化，就返回这个序列的第一个方向和平均分。如果所有序列都无法使棋盘发生变化，就返回最后一个序列的第一个方向和平均分'''



class Ai:
    def __init__(self):
        self.g = Grid(config.SIZE)

    def get_next(self, tiles):
        score_list = []
        tn = self.get_num(tiles)
        if tn >= self.g.size ** 2 / 3:
            return "RD"[np.random.randint(0, 2)], 0
        kn = min(max(tn ** 2, 20), 40)
        for directions in itertools.product("ULRD", repeat=3):
            fen = []
            for i in range(kn):
                t_g = get_grid(tiles, directions)
                fen.append(self.get_score(t_g))
            print(directions, min(fen))
            score_list.append([directions, min(fen)])
        score_list = sorted(score_list, key=(lambda x: [x[1]]))
        # print(score_list)
        for d in score_list[::-1]:
            self.g.tiles = tiles.copy()
            if self.g.run(d[0][0], is_fake=False) != 0:
                return d[0][0], d[1] / kn
        self.g.tiles = tiles.copy()
        # print('===',score_list[-1][0][0])
        return score_list[-1][0][0], score_list[-1][1] / kn


    '''这个方法接受一个参数 tiles，表示棋盘的状态，它的作用是计算当前棋盘的分数。

    这个方法中，最开始的三行注释掉的代码会使用 get_bj2() 和 get_bj() 两个方法计算出当前棋盘的四个角的分数，然后返回最高的分数。

    目前的实现中，这个方法使用的是 get_bj2__4() 和 get_bj__4() 两个方法计算四个角的分数之和，然后将这个值乘以 2.8 并加上 get_bj__4() 返回的值，最后返回计算的结果。'''
    def get_score(self, tiles):
        a = self.get_bj2__4(tiles)
        b = self.get_bj__4(tiles)
        print(a, b)
        return a * 2.8 + b




    def debug(self, tiles):
        print('\n=======开始判断========')
        print('移动前棋盘：')
        printf(tiles)
        score_list = []
        for directions in itertools.product("ULRD", repeat=2):
            t_g = get_grid(tiles, directions)
            fen = self.get_score(t_g)
            score_list.append([directions, fen])
            print('==={}=={}=='.format(directions, fen))
            printf(t_g)
        score_list = sorted(score_list, key=(lambda x: [x[1]]))
        # print(score_list)
        for d in score_list[::-1]:
            # print('-->',d)
            self.g.tiles = tiles.copy()
            # print(self.g.run(d[0][0],is_fake=True))
            if self.g.run(d[0][0], is_fake=True) != 0:
                # print('---异动前：')
                # print(self.g.tiles)
                # print('---异动后：')
                self.g.run(d[0][0])
                # print(self.g.tiles)
                return d[0][0]
        # print('===',score_list[-1][0][0])
        return score_list[-1][0][0]

    '''get_num() 方法用于计算当前棋盘上有多少个格子是已经有数字的。它首先将棋盘的状态转换为一个 NumPy 数组，然后使用 NumPy 的 nonzero() 方法计算出数组中非零元素的个数。'''
    def get_num(self, tiles):
        # l = len(tiles)
        n = 0
        for row in tiles:
            for i in row:
                if i == 0:
                    n += 1
        return n
        # return np.bincount(tiles)[0]

    def get_bj(self, tiles):
        gjs = [
            self.get_bj__1(tiles),
            self.get_bj__2(tiles),
            self.get_bj__3(tiles),
            self.get_bj__4(tiles)
        ]
        return gjs

    def get_bj__4(self, tiles):
        bj = 0
        l = len(tiles)
        size = self.g.size - 1
        for y in range(l):
            for x in range(l):
                z = tiles[y][x]
                if z != 0:
                    z_log = z - 2
                    bj += z_log * (x + y - (size * 2 - 1))
                else:
                    bj += (100 - 20 * (x + y - (size * 2 - 1)))
                # print(z, "-- ", bj)
        return bj

    def get_bj__3(self, tiles):
        bj = 0
        l = len(tiles)
        size = self.g.size - 1
        for y in range(l):
            for x in range(l):
                z = tiles[y][x]
                if z != 0:
                    z_log = z - 2
                    bj += z_log * ((size - x) + y - (size * 2 - 1))
                else:
                    bj += (100 - 20 * ((size - x) + y - (size * 2 - 1)))
        return bj

    def get_bj__2(self, tiles):
        bj = 0
        l = len(tiles)
        size = self.g.size - 1
        for y in range(l):
            for x in range(l):
                z = tiles[y][x]
                if z != 0:
                    z_log = z - 2
                    bj += z_log * ((size - x) + (size - y) - (size * 2 - 1))
                else:
                    bj += (100 - 20 * ((size - x) + (size - y) - (size * 2 - 1)))
        return bj

    def get_bj__1(self, tiles):
        bj = 0
        l = len(tiles)
        size = self.g.size - 1
        for y in range(l):
            for x in range(l):
                z = tiles[y][x]
                if z != 0:
                    z_log = z - 2
                    bj += z_log * (x + (size - y) - (size * 2 - 1))
                else:
                    bj += (100 - 20 * (x + (size - y) - (size * 2 - 1)))
        return bj

    def get_bj2(self, tiles):
        gjs = [
            self.get_bj2__1(tiles),
            self.get_bj2__2(tiles),
            self.get_bj2__3(tiles),
            self.get_bj2__4(tiles)
        ]
        return gjs

    def get_bj2__1(self, tiles):
        bj = 0
        l = len(tiles)
        for y in range(0, l - 1, 1):
            for x in range(l - 1, 0, -1):
                z = tiles[y][x]
                if tiles[y][x] < tiles[y][x - 1]:
                    bj -= abs(H(tiles[y][x - 1]) - z)
                if tiles[y][x] < tiles[y + 1][x]:
                    bj -= abs(H(tiles[y + 1][x]) - z)
                if tiles[y][x] < tiles[y + 1][x - 1]:
                    bj -= abs(H(tiles[y + 1][x - 1]) - z)
        return bj

    def get_bj2__2(self, tiles):
        bj = 0
        l = len(tiles)
        for y in range(0, l - 1):
            for x in range(0, l - 1):
                z = tiles[y][x]
                if tiles[y][x] < tiles[y][x + 1]:
                    bj -= abs(H(tiles[y][x + 1]) - z)
                if tiles[y][x] < tiles[y + 1][x]:
                    bj -= abs(H(tiles[y + 1][x]) - z)
                if tiles[y][x] < tiles[y + 1][x + 1]:
                    bj -= abs(H(tiles[y + 1][x + 1]) - z)
        return bj

    def get_bj2__3(self, tiles):
        bj = 0
        l = len(tiles)
        for y in range(l - 1, 0, -1):
            for x in range(0, l - 1):
                z = tiles[y][x]
                if tiles[y][x] < tiles[y][x + 1]:
                    bj -= abs(H(tiles[y][x + 1]) - z)
                if tiles[y][x] < tiles[y - 1][x]:
                    bj -= abs(H(tiles[y - 1][x]) - z)
                if tiles[y][x] < tiles[y - 1][x + 1]:
                    bj -= abs(H(tiles[y - 1][x + 1]) - z)
        return bj

    def get_bj2__4(self, tiles):
        bj = 0
        l = len(tiles)
        for y in range(l - 1, 0, -1):
            for x in range(l - 1, 0, -1):
                z = tiles[y][x]
                if z < tiles[y][x - 1]:
                    bj -= abs(H(tiles[y][x - 1]) - z)
                if z < tiles[y - 1][x]:
                    bj -= abs(H(tiles[y - 1][x]) - z)
                if z < tiles[y - 1][x - 1]:
                    bj -= abs(H(tiles[y - 1][x - 1]) - z)
        return bj


if __name__ == '__main__':
    game = Game(4)
    game.grid.tiles = np.array([
        [0, 0, 0, 0],
        [0, 32, 64, 128],
        [256, 512, 1024, 1024],
        [1024, 1024, 1024, 1024]
    ])
    ai = Ai()
    print(game.grid)

    a = ai.get_next(game.grid.tiles)
    print(a)
    game.run(a[0])
    print(game.grid)
