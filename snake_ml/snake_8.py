from collections import deque
import pygame
from random import randrange
from pygame.locals import *
from réseaux.Multi_layer_NN import *
import math


class Vector(tuple):
    """A tuple that supports some vector operations.

    v, w = Vector((1, 2)), Vector((3, 4))
    v + w, w - v, v * 10, 100 * v, -v
    ((4, 6), (2, 2), (10, 20), (100, 200), (-1, -2))
    """
    def __add__(self, other):
        return Vector(v + w for v, w in zip(self, other))

    def __radd__(self, other):
        return Vector(w + v for v, w in zip(self, other))

    def __sub__(self, other):
        return Vector(v - w for v, w in zip(self, other))

    def __rsub__(self, other):
        return Vector(w - v for v, w in zip(self, other))

    def __mul__(self, s):
        return Vector(v * s for v in self)

    def __rmul__(self, s):
        return Vector(v * s for v in self)

    def __neg__(self):
        return -1 * self


FPS = 60                        # Game frames per second
SEGMENT_SCORE = 1               # Score per segment

SNAKE_SPEED_INCREMENT = 0.25    # Snake speeds up this much each time it grows
SNAKE_START_LENGTH = 5          # Initial snake length in segments

WORLD_SIZE = Vector((20, 20))   # World size, in blocks
BLOCK_SIZE = 24                 # Block size, in pixels

BACKGROUND_COLOR = 0, 0, 0
SNAKE_COLOR = 255, 255, 255
FOOD_COLOR = 255, 0, 0
DEATH_COLOR = 255, 0, 0
TEXT_COLOR = 255, 255, 255

DIRECTION_UP    = Vector((0, -1))
DIRECTION_DOWN  = Vector((0,  1))
DIRECTION_LEFT  = Vector((-1,  0))
DIRECTION_RIGHT = Vector((1,  0))
DIRECTION_DR    = DIRECTION_DOWN + DIRECTION_RIGHT

# Map from PyGame key event to the corresponding direction.
KEY_DIRECTION = {
    K_q: DIRECTION_UP,    K_UP:    DIRECTION_UP,
    K_s: DIRECTION_DOWN,  K_DOWN:  DIRECTION_DOWN,
    K_a: DIRECTION_LEFT,  K_LEFT:  DIRECTION_LEFT,
    K_d: DIRECTION_RIGHT, K_RIGHT: DIRECTION_RIGHT,
}


class Snake(object):
    def __init__(self, start, timer, start_length, pot_parents, scores_p,
                 proportion, amplitude, batch, speed, loaded, struct):
        self.speed = speed                # Speed in squares per second.
        self.timer = 1.0 / self.speed     # Time remaining to next movement.
        self.growth_pending = 0           # Number of segments still to grow.
        self.direction = DIRECTION_UP     # Current movement direction.
        self.segments = deque([start - self.direction * i for i in range(start_length)])
        self.bool_timer = timer
        # juste une liste de tuple contenant les coordonnées des blocks du snake [(xhead, yhead), (xsec, ysec),...]
        if type(pot_parents) == str and loaded:
            # take a pre-trained snake and evolve it more
            self.brain = MLNeuralNetwork(pot_parents)
            self.brain.mutate(proportion, amplitude)
        elif type(pot_parents) == str and not loaded:
            # visualise snake
            self.brain = MLNeuralNetwork(pot_parents)
        elif type(pot_parents) == MLNeuralNetwork:
            self.brain = pot_parents
            self.brain.mutate(proportion, amplitude)
        else:
            if len(pot_parents) == 0:
                # initialise random snakes
                structure = np.concatenate(([24], struct, [4])).tolist()
                self.brain = MLNeuralNetwork(structure)
            else:
                parents = pooling(pot_parents, scores_p).tolist()
                self.brain = MLNeuralNetwork(parents)
                self.brain.mutate(proportion, amplitude)
                """
                if batch == 0:
                    self.brain = pot_parents[0]
                else:
                    parents = pooling(pot_parents, scores_p).tolist()
                    self.brain = MLNeuralNetwork(parents)
                    self.brain.mutate(proportion, amplitude)"""

    def __iter__(self):
        return iter(self.segments)

    def __len__(self):
        return len(self.segments)

    def head(self):
        """Return the position of the snake's head."""
        return self.segments[0]

    def update(self, dt, x_head, y_head, screen_size, moves, tot_moves):
        """Update the snake by dt seconds and possibly set direction."""
        if self.bool_timer:
            self.timer -= dt
            if self.timer > 0:
                # Nothing to do yet.
                return moves, tot_moves

        obs = see(x_head, y_head, self.segments, screen_size)
        actions = self.brain.think(obs)
        actions = choice(actions)

        if actions[0] == 1:
            direction = DIRECTION_UP

        if actions[1] == 1:
            direction = DIRECTION_DOWN

        if actions[2] == 1:
            direction = DIRECTION_RIGHT

        if actions[3] == 1:
            direction = DIRECTION_LEFT

        if self.direction != -direction:
            self.direction = direction

        self.timer += 1 / self.speed
        # Add a new head.
        self.segments.appendleft(self.head() + self.direction)
        if self.growth_pending > 0:
            self.growth_pending -= 1
        else:
            # Remove tail.
            self.segments.pop()
        return moves - 1, tot_moves + 1

    def grow(self):
        """Grow snake by one segment and speed up."""
        self.growth_pending += 1
        self.speed += SNAKE_SPEED_INCREMENT

    def self_intersecting(self):
        """Is the snake currently self-intersecting?"""
        it = iter(self)
        head = next(it)
        return head in it


class SnakeGame(object):
    def __init__(self, parents, scores_p, structure,
                 proportion, amplitude, moves, add_moves,
                 generation, screen, speed, size, loaded, n_batch, bool_speed, n_eval):
        pygame.display.set_caption('PyGame Snake')
        self.block_size = BLOCK_SIZE
        self.see = screen
        self.size = size
        if self.see:
            self.window = pygame.display.set_mode(Vector((size, size)) * self.block_size) #turn off if doesn't want to see the screen
        self.screen = pygame.display.get_surface()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font('freesansbold.ttf', 20)
        self.world = Rect((0, 0), Vector((size, size)))
        self.reset(parents, scores_p, proportion, amplitude, 0, speed, loaded, structure, bool_speed, True)
        self.moves = moves
        self.add_moves = add_moves
        self.generation = generation
        self.batch = 0
        self.brains = np.empty(n_batch, dtype=tuple)
        self.n_batch = n_batch

        self.parents = parents
        self.scores_p = scores_p
        self.proportion = proportion
        self.amplitude = amplitude
        self.speed = speed
        self.loaded = loaded
        self.structure = structure
        self.save_moves = moves
        self.moves_done = 0
        self.n_eval = n_eval

    def reset(self, parents, scores_p, proportion, amplitude, batch, speed, loaded, structure, bool_speed, reset_brain):
        """Start a new game."""
        self.playing = True
        self.next_direction = DIRECTION_UP
        self.score = 0
        self.moves_done = 0
        self.bool_speed = bool_speed
        if reset_brain:
            self.snake = Snake(self.world.center, bool_speed, SNAKE_START_LENGTH,
                                parents, scores_p, proportion,
                                amplitude, batch, speed, loaded, structure)
        else:
            self.snake.direction = DIRECTION_UP
            self.snake.segments = deque([self.world.center - self.snake.direction * i
                                         for i in range(SNAKE_START_LENGTH)])
            self.snake.speed = speed
            self.snake.timer = 1.0 / self.snake.speed
            self.snake.bool_timer = bool_speed
            self.snake.growth_pending = 0
        # à modifier en boucle for
        self.food = set()
        self.add_food()

    def add_food(self):
        """Ensure that there is at least one piece of food.
        (And, with small probability, more than one.)
        """
        while not (self.food and randrange(4)):
            global food
            food = Vector(map(randrange, self.world.bottomright))
            if food not in self.food and food not in self.snake \
                    and food[0] != self.world.center[0] \
                    and food[1] != self.world.center[1] - 1:
                self.food.add(food)
                break  # comme ça il en crée pas plusieurs ce con

    def input(self, e):
        """Process keyboard event e."""
        if e.key in KEY_DIRECTION:
            self.next_direction = KEY_DIRECTION[e.key]

    def brain_action(self, actions):  # unused for the moment
        #print(actions)

        if actions[0] == 1:
            self.next_direction = DIRECTION_UP

        if actions[1] == 1:
            self.next_direction = DIRECTION_DOWN

        if actions[2] == 1:
            self.next_direction = DIRECTION_RIGHT

        if actions[3] == 1:
            self.next_direction = DIRECTION_LEFT

    def update(self, dt, x_head, y_head, screen_size):
        """Update the game by dt seconds."""
        self.moves, self.moves_done = self.snake.update(dt, x_head, y_head, screen_size, self.moves, self.moves_done)



        # If snake hits a food block, then consume the food, add new
        # food and grow the snake.
        head = self.snake.head()
        if head in self.food:
            self.food.remove(head)
            self.add_food()
            self.snake.grow()
            self.score += 1 #len(self.snake) * SEGMENT_SCORE
            self.moves += self.add_moves

        # If snake collides with self or the screen boundaries, then
        # it's game over.
        if self.snake.self_intersecting() or not self.world.collidepoint(self.snake.head()):
            self.playing = False

    def block(self, p):
        """Return the screen rectangle corresponding to the position p."""
        return Rect(p * self.block_size, DIRECTION_DR * self.block_size)

    def draw_text(self, text, p):
        """Draw text at position p."""
        self.screen.blit(self.font.render(text, 1, TEXT_COLOR), p)

    def draw(self):
        """Draw game (while playing)."""
        self.screen.fill(BACKGROUND_COLOR)
        for p in self.snake:
            pygame.draw.rect(self.screen, SNAKE_COLOR, self.block(p))
        for f in self.food:
            pygame.draw.rect(self.screen, FOOD_COLOR, self.block(f))
        self.draw_text("Score: {}".format(self.score), (20, 20))
        self.draw_text("Moves left: {}".format(self.moves), (20, 40))
        self.draw_text("generation: {}".format(self.generation), (20, 60))
        self.draw_text("batch: {}".format(self.batch), (20, 80))

    def draw_death(self):
        """Draw game (after game over)."""
        self.screen.fill(DEATH_COLOR)
        self.draw_text("Game over! Press Space to start a new game", (20, 150))
        self.draw_text("Your score is: {}".format(self.score), (140, 180))

    @property
    def play(self):
        """Play game until the QUIT event is received."""
        tik = 1/self.snake.speed
        play = True
        count_eval = 0
        b_scores = np.zeros(self.n_eval)
        while True:
            dt = self.clock.tick(FPS) / 1000.0  # convert to seconds

            for e in pygame.event.get():
                if e.type == QUIT:
                    return
                elif e.type == K_e:
                    continue
                elif pygame.mouse.get_pressed()[0] and play:
                    play = False
                elif pygame.mouse.get_pressed()[0] and not play:
                    play = True


            if self.moves == 0:
                count_eval += 1
                if count_eval < self.n_eval:
                    reset_brain = False
                    b_scores[count_eval - 1] = self.score  # fitness(self.moves_done, self.score)

                else:
                    reset_brain = True
                    b_scores[count_eval - 1] = self.score
                    self.snake.brain.score = math.floor(np.sum(b_scores) / self.n_eval)
                    self.brains[self.batch] = self.snake.brain
                    b_scores = np.zeros(self.n_eval)
                    self.batch += 1
                    count_eval = 0

                if self.batch == self.n_batch:
                    return self.brains

                self.reset(self.parents, self.scores_p, self.proportion, self.amplitude,
                           self.batch, self.speed, self.loaded, self.structure, self.bool_speed, reset_brain)
                self.moves = self.save_moves

            if self.moves_done > 500:
                count_eval += 1
                if count_eval < self.n_eval:
                    reset_brain = False
                    b_scores[count_eval - 1] = self.score  # fitness(self.moves_done, self.score)

                else:
                    b_scores[count_eval - 1] = self.score
                    reset_brain = True
                    self.snake.brain.score = math.floor(np.sum(b_scores) / self.n_eval)
                    self.brains[self.batch] = self.snake.brain
                    b_scores = np.zeros(self.n_eval)
                    self.batch += 1
                    count_eval = 0

                if self.batch == self.n_batch:
                    return self.brains

                self.reset(self.parents, self.scores_p, self.proportion, self.amplitude,
                           self.batch, self.speed, self.loaded, self.structure, self.bool_speed, reset_brain)
                self.moves = self.save_moves



            if self.playing and play:
                self.update(dt, food[0], food[1], self.size)
                if self.see:
                    self.draw()
            elif not self.playing:
                count_eval += 1
                if count_eval < self.n_eval:
                    reset_brain = False
                    b_scores[count_eval - 1] = self.score  # fitness(self.moves_done, self.score)

                else:
                    reset_brain = True
                    b_scores[count_eval - 1] = self.score
                    self.snake.brain.score = math.floor(np.sum(b_scores) / self.n_eval)
                    self.brains[self.batch] = self.snake.brain
                    b_scores = np.zeros(self.n_eval)
                    self.batch += 1
                    count_eval = 0

                if self.batch == self.n_batch:
                    return self.brains

                self.reset(self.parents, self.scores_p, self.proportion, self.amplitude,
                           self.batch, self.speed, self.loaded, self.structure, self.bool_speed, reset_brain)
                self.moves = self.save_moves

            if self.see:
                pygame.display.flip()


def fitness(moves, score):
    if score == 0:
        return 0
    if score == 1:
        return math.floor(moves**2/100)
    if score < 10:
        return math.floor(moves**2/50) * 2**score
    else:
        return math.floor(moves**2/50) * 2**score * (score - 9)


def see(x_food, y_food, segments, screen_size):
    """
    return the observations in a list of size 24
    8 first element are the distances to the food, from 0 to 1 if it is close
    then distances to the wall
    then distances to the snake himself
    :param x_food: x-coordinate of the food
    :param y_food: y-coordinate of the food
    :param segments: list of tuple (x, y) of the snake
    :param screen_size: size of the screen in blocks
    :return: array containing all the observations
    """
    screen_size -= 1
    observations = np.zeros(24)
    x_head = segments[0][0]
    y_head = segments[0][1]
    #print(x_head)
    #print(y_head)
    # FOOD
    # food above or under
    if x_food == x_head:
        # food up
        if y_head > y_food:
            observations[0] += -y_head + y_food + screen_size
            observations[0] = screen_size
        # food down
        else:
            observations[4] += -y_food + y_head + screen_size
            observations[4] = screen_size

    # food right or left
    if y_food == y_head:
        # food right
        if x_head < x_food:
            observations[2] += -x_food + x_head + screen_size
            observations[2] = screen_size
        # food left
        else:
            observations[6] += -x_head + x_food + screen_size
            observations[6] = screen_size

    # food up right and down left
    if (x_food + y_food) == (x_head + y_head):
        # food up right
        if x_head < x_food:
            observations[1] += screen_size - 2 * (y_head - y_food)
            observations[1] = screen_size
        # food down left
        else:
            observations[5] += screen_size - 2 * (y_food - y_head)
            observations[5] = 1

    # food up left and down right
    if (y_head - x_head) == (y_food - x_food):
        # food under right
        if x_head < x_food:
            observations[3] += screen_size - 2 * (x_food - x_head)
            observations[3] = screen_size
        # food up left
        else:
            observations[7] += screen_size + 2 * (x_head -x_food)
            observations[7] = screen_size

    # WALL
    # wall up
    observations[8] += screen_size - y_head

    # wall down
    observations[12] += y_head

    # wall right
    observations[10] += x_head

    # wall left
    observations[14] += screen_size - x_head

    # walls on the sight
    if (x_head + y_head) > screen_size:  # /
        # wall top right
        if (screen_size - x_head) == 0:
            observations[9] = screen_size
        else:
            observations[9] += screen_size - 2 * (screen_size - x_head)
        # wall down left
        if (screen_size - y_head) == 0:
            observations[13] = screen_size
        else:
            observations[13] += screen_size - 2 * (screen_size - y_head)
    else:
        # wall top right
        if y_head == 0:
            observations[9] = screen_size
        else:
            observations[9] += screen_size - 2 * y_head
        # wall down left
        if x_head == 0:
            observations[13] = screen_size
        else:
            observations[13] += screen_size - 2 * x_head

    if x_head > y_head:  # \
        # wall down right
        if (screen_size - x_head) == 0:
            observations[11] = screen_size
        else:
            observations[11] += screen_size - 2 * (screen_size - x_head)
        # wall up left
        if y_head == 0:
            observations[15] = screen_size
        else:
            observations[15] += screen_size - 2 * y_head
    else:
        # wall down right
        if (screen_size - y_head) == 0:
            observations[11] = screen_size
        else:
            observations[11] += screen_size - 2 * (screen_size - y_head)
        # wall up left
        if x_head == 0:
            observations[15] = screen_size
        else:
            observations[15] += screen_size - 2 * x_head


    # TAIL
    for coord in segments:
        x_tail = coord[0]
        y_tail = coord[1]

        # tail up or down
        if x_tail == x_head:
            # tail up
            if y_head > y_tail and (observations[16] < -(y_head - y_tail) or observations[16] == 0):
                observations[16] = -(y_head - y_tail) + screen_size
                observations[16] = screen_size
            # tail down
            if y_tail > y_head and (observations[20] < -(y_tail - y_head) or observations[20] == 0):
                observations[20] = -(y_tail - y_head) + screen_size
                observations[20] = screen_size

        # tail right or left
        if y_tail == y_head:
            # tail right
            if x_head < x_tail and (observations[18] < -(x_tail - x_head) or observations[18] == 0):
                observations[18] = -(x_tail - x_head) + screen_size
                observations[18] = screen_size
            # tail left
            if x_tail < x_head and (observations[22] < -(x_head - x_tail) or observations[22] == 0):
                observations[22] = -(x_head - x_tail) + screen_size
                observations[22] = screen_size

        # tail up right and down left
        if (x_tail + y_tail) == (x_head + y_head):
            # tail up right
            if x_head < x_tail and \
                    (observations[17] < -((y_head - y_tail) + (x_tail - x_head)) or observations[17] == 0):
                observations[17] = -((y_head - y_tail) + (x_tail - x_head)) + screen_size
                observations[17] = screen_size
            # tail down left
            if x_tail < x_head and \
                    (observations[21] < -((y_tail - y_head) + (x_head - x_tail)) or observations[21] == 0):
                observations[21] = -((y_tail - y_head) + (x_head - x_tail)) + screen_size
                observations[21] = screen_size

        # tail up left and down right
        if (y_head - x_head) == (y_tail - x_tail):
            # tail under right
            if x_head < x_tail \
                    and (observations[19] < -((x_tail - x_head) + (y_tail - y_head)) or observations[19] == 0):
                observations[19] = -((x_tail - x_head) + (y_tail - y_head)) + screen_size
                observations[19] = screen_size
            # tail up left
            if x_tail < x_head and \
                    (observations[23] < -((x_head - x_tail) + (y_head - y_tail)) or observations[23] == 0):
                observations[23] = -((x_head - x_tail) + (y_head - y_tail)) + screen_size
                observations[23] = screen_size

    # adding the screen size to the negative values to make the obstacles that are closer, bigger.
    # normalising the inputs
    observations /= screen_size
    #print(observations)
    return observations
