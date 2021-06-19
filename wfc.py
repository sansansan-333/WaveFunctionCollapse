import sys
from PIL import Image
import uuid
import random
import copy
import time
from functools import lru_cache

class Pixel:
    def __init__(self, rgba:tuple):
        self.r = rgba[0]
        self.g = rgba[1]
        self.b = rgba[2]
        self.a = rgba[3]

    def get_pixel(self):
        return (self.r, self.g, self.b, self.a)

class Pattern:
    def __init__(self, size:tuple):
        self.uid = uuid.uuid4()
        self.pixels = []
        self.adjacency_pixels = {} # UUID -> Pattern

class Wave:
    def __init__(self):
        self.patterns_uid = []

    def get_entropy(self):
        return len(self.patterns_uid)

class Index:
    def __init__(self):
        self.data = {}

    def construct(self, patterns_uid:list):
        for uid in patterns_uid:
            self.data[uid] = {}
            for d in [(1, 0), (0, 1), (0, -1), (-1, 0)] + [(-1, 1), (-1, -1), (1, 1), (1, -1)]:
                self.data[uid][d] = []
    
    def add_rule(self, pattern_uid:uuid.UUID, relative_pos:tuple, next_pattern_uid:uuid.UUID):
        self.data[pattern_uid][relative_pos].append(next_pattern_uid)

    @lru_cache(maxsize=128)
    def check(self, pattern_uid:uuid.UUID, relative_pos:tuple, check_pattern_uid:uuid.UUID):
        t1 = time.time()

        result = check_pattern_uid in self.data[pattern_uid][relative_pos]

        t2 = time.time()
        wfc.execution_t[self.check.__name__] += t2-t1
        wfc.execution_n[self.check.__name__] += 1

        return result


### Overlapping model ###
class WFC:
    def __init__(self, image_path:str, extract_size:tuple, output_size:tuple, rotate=True, diagnal_check=True):
        self._rotate = rotate
        if rotate and extract_size[0] != extract_size[1]:
            print("Error: Extract size must be rectangle if rotate is on.")
            sys.exit()
        self._diagnal_check = diagnal_check
            
        self._image = Image.open(image_path).convert('RGBA')
        self._input_size = self._image.size
        self._extract_size = extract_size
        self._output_size = output_size

        #self._waves = [[tmpWave] * 4 for i in range(5)] # 5 x 4 の wave array
        self._patterns = {} # uid -> pattern
        self._coefficient = [[True] * int(output_size[1]/extract_size[1]) \
                                    for _ in range(int(output_size[0]/extract_size[0]))] 
        self._waves = [[Wave()] * int(output_size[1]/extract_size[1]) \
                                    for _ in range(int(output_size[0]/extract_size[0]))] 
        # init wave array(上の書き方だと同じアドレスを一部で共有してるので、それを切る)
        for col in range(len(self._waves)):
            for row in range(len(self._waves[0])):
                self._waves[col][row] = Wave()

        self.index = Index()
        self.neighbour_data = {} # pattern uid -> direction -> list of possible neighbouring pattern

        # for debugging
        self.execution_t = { # function name -> sum of execution time
            'total': 0,
            self._get_possible_neighbours_uid.__name__: 0, 
            self._get_neighboring_cells.__name__: 0,
            self._is_match_pattern.__name__: 0,
            self._vec2dir.__name__: 0,
            self._2dim_pixels.__name__: 0,
            Index.check.__name__: 0
        }
        self.execution_n = { # function name -> number of times the function has been called
            self._get_possible_neighbours_uid.__name__: 0, 
            self._get_neighboring_cells.__name__: 0,
            self._is_match_pattern.__name__: 0,
            self._vec2dir.__name__: 0,
            self._2dim_pixels.__name__: 0,
            Index.check.__name__: 0
        }

    def do_magic(self): # OK
        t1 = time.time()

        self._extract_data()

        while not self._is_fully_collapsed():
            self._iterate()
        self._get_result_img().show()

        t2 = time.time()
        self.execution_t['total'] += t2-t1
        self.output_execution_analysis()

    def _extract_data(self):
        img = self._image
        input_size = self._input_size
        extract_size = self._extract_size

        # test image gathered from all extracted patterns(unexpectedly interesting!)
        ###testImg = Image.new('RGBA', ((input_size[1]-extract_size[1]+1)*extract_size[1], (input_size[0]-extract_size[0]+1)*extract_size[0]))

        # extract patterns
        for y in range(1, input_size[0]-extract_size[0]):
            for x in range(1, input_size[1]-extract_size[1]):
                tmp_pattern = Pattern(extract_size)
                # extract center pixels of the pattern
                for patternY in range(y, y + extract_size[0]):
                    for patternX in range(x, x + extract_size[1]):
                        tmp_pattern.pixels.append(Pixel(img.getpixel((patternX, patternY))))
                        ###testImg.putpixel((x*extract_size[1]+patternX-x, y*extract_size[0]+patternY-y), tmpPattern.pixels[len(tmpPattern.pixels)-1].get_pixel())
                
                # extract adjacency pixels of the pattern
                tmpAdjPixels = {}
                tmpAdjPixels['ul'] = Pixel(img.getpixel((x-1, y-1)))
                tmpAdjPixels['ur'] = Pixel(img.getpixel((x+extract_size[1], y-1)))
                tmpAdjPixels['dl'] = Pixel(img.getpixel((x-1, y+extract_size[0])))
                tmpAdjPixels['dr'] = Pixel(img.getpixel((x+extract_size[1], y+extract_size[0])))
                for adjX in range(x, x+extract_size[1]):
                    key = 'u' + str(adjX-x)
                    tmpAdjPixels[key] = Pixel(img.getpixel((adjX, y-1)))
                    key = 'd' + str(adjX-x)
                    tmpAdjPixels[key] = Pixel(img.getpixel((adjX, y+extract_size[0])))
                for adjY in range(y, y+extract_size[0]):
                    key = 'l' + str(adjY-y)
                    tmpAdjPixels[key] = Pixel(img.getpixel((x-1, adjY)))
                    key = 'r' + str(adjY-y)
                    tmpAdjPixels[key] = Pixel(img.getpixel((x+extract_size[1], adjY)))
                tmp_pattern.adjacency_pixels = tmpAdjPixels

                # set patterns
                if not self._is_existing_pattern(tmp_pattern, self._patterns):
                    self._patterns[tmp_pattern.uid] = tmp_pattern

        if self._rotate:
            # rotate
            rotated_patterns = []
            for pattern_uid in self._patterns.values():
                rotated_pattern = self._rotate_pattern(pattern_uid)
                rotated_patterns.extend(rotated_pattern)
            for pattern_uid in rotated_patterns:
                if not self._is_existing_pattern(pattern_uid, self._patterns):
                    self._patterns[pattern_uid.uid] = pattern_uid
            # flip
            flipped_patterns = []
            for pattern_uid in self._patterns.values():
                flipped_pattern = self._flip_pattern(pattern_uid)
                flipped_patterns.append(flipped_pattern)
            for pattern_uid in flipped_patterns:
                if not self._is_existing_pattern(pattern_uid, self._patterns):
                    self._patterns[pattern_uid.uid] = pattern_uid

        # construct waves
        for col in range(len(self._waves)):
            for row in range(len(self._waves[0])):
                for key in self._patterns:
                    self._waves[col][row].patterns_uid.append(key)

        # construct index
        self.index.construct(self._patterns.keys())
        for uid in self._patterns.keys():
            for uid_next in self._patterns.keys():
                for d in [(1, 0), (0, 1), (0, -1), (-1, 0)] + [(-1, 1), (-1, -1), (1, 1), (1, -1)]:
                    if self._is_match_pattern(self._patterns[uid], d, self._patterns[uid_next]):
                        self.index.add_rule(uid, d, uid_next)

        # create matching data
        for pattern_uid in self._patterns.keys():
            self.neighbour_data[pattern_uid] = {}
            dir = [(1, 0), (0, 1), (0, -1), (-1, 0)]
            if self._diagnal_check:
                dir += [(-1, 1), (-1, -1), (1, 1), (1, -1)]
            for d in dir:
                self.neighbour_data[pattern_uid][d] = []
                for next_pattern_uid in self._patterns.keys():
                    if self.index.check(pattern_uid, d, next_pattern_uid):
                        self.neighbour_data[pattern_uid][d].append(next_pattern_uid)
            
                
        ###testImg.show()

    def _rotate_pattern(self, pattern:Pattern):
        """
        Return a list contains rotated patterns with 90, 180 and 270 degree.
        Notice basically this function will be called if self._rotate_flag is true, meaning extract size is rectangle.
        (But different condition is also considered in this function.)
        """
        result_patterns = []
        extract_size = self._extract_size
        original_pixels = self._2dim_pixels(pattern.pixels, extract_size)
        original_adj_pixels = pattern.adjacency_pixels
        # theta = 90 x 3 times
        for _ in range(3):
            rotated_pattern = Pattern(extract_size)
            pixels = []
            adj_pixels = {}
            # rotate pixels
            for x in range(extract_size[1]):
                for y in range(extract_size[0]):
                    pixels.append(original_pixels[y][extract_size[1]-1-x])
            # rotate adjacent pixels
            adj_pixels['ul'] = original_adj_pixels['ur']
            adj_pixels['ur'] = original_adj_pixels['dr']
            adj_pixels['dl'] = original_adj_pixels['ul']
            adj_pixels['dr'] = original_adj_pixels['dl']
            for y in range(extract_size[1]):
                d = 'l' + str(y)
                d_orig = 'u' + str(extract_size[1]-1-y)
                adj_pixels[d] = original_adj_pixels[d_orig]
                d = 'r' + str(y)
                d_orig = 'd' + str(extract_size[1]-1-y)
                adj_pixels[d] = original_adj_pixels[d_orig]
            for x in range(extract_size[0]):
                d = 'u' + str(x)
                d_orig = 'r' + str(x)
                adj_pixels[d] = original_adj_pixels[d_orig]
                d = 'd' + str(x)
                d_orig = 'l' + str(x)
                adj_pixels[d] = original_adj_pixels[d_orig]

            rotated_pattern.pixels = pixels
            rotated_pattern.adjacency_pixels = adj_pixels
            result_patterns.append(rotated_pattern)

            # copy
            original_pixels = self._2dim_pixels(rotated_pattern.pixels, extract_size)
            original_adj_pixels = rotated_pattern.adjacency_pixels

        return result_patterns

    def _flip_pattern(self, pattern:Pattern):
        """
        Return the flipped pattern with Y axis.
        """
        extract_size = self._extract_size
        result_pattern = Pattern(extract_size)
        pixels = []
        adj_pixels = {}

        original_pixels = self._2dim_pixels(pattern.pixels, extract_size)
        original_adj_pixels = pattern.adjacency_pixels
        # flip center pixels
        for y in range(extract_size[0]):
            for x in range(extract_size[1]):
                pixels.append(original_pixels[y][extract_size[1]-1-x])
        # flip adj pixels
        adj_pixels['ul'] = original_adj_pixels['ur']
        adj_pixels['ur'] = original_adj_pixels['ul']
        adj_pixels['dl'] = original_adj_pixels['dr']
        adj_pixels['dr'] = original_adj_pixels['dl']
        for y in range(extract_size[0]):
            adj_pixels['l' + str(y)] = original_adj_pixels['r' + str(y)]
            adj_pixels['r' + str(y)] = original_adj_pixels['l' + str(y)]
        for x in range(extract_size[1]):
            adj_pixels['u' + str(x)] = original_adj_pixels['u' + str(extract_size[1]-1-x)]
            adj_pixels['d' + str(x)] = original_adj_pixels['d' + str(extract_size[1]-1-x)]
        # set data
        result_pattern.pixels = pixels
        result_pattern.adjacency_pixels = adj_pixels

        return result_pattern

    def _is_existing_pattern(self, pattern:Pattern, pattern_list:dict): # OK
        if len(pattern_list) == 0:
            return False

        extract_size = self._extract_size
        dir = [(1, 0), (0, 1), (0, -1), (-1, 0)] + [(-1, 1), (-1, -1), (1, 1), (1, -1)]
        dirs_str = []
        for d in dir:
            dirs_str.extend(self._vec2dir(d, extract_size))
        same_flag = True

        extract_size = self._extract_size
        for cur_pattern in pattern_list.values():
            # center
            i = 0
            for _ in range(extract_size[0]):
                for _ in range(extract_size[1]):
                    if not cur_pattern.pixels[i].get_pixel() == pattern.pixels[i].get_pixel():
                        same_flag = False
                    i+=1
            # adj
            for dir_str in dirs_str:
                if not cur_pattern.adjacency_pixels[dir_str].get_pixel() == pattern.adjacency_pixels[dir_str].get_pixel():
                    same_flag = False

            if same_flag:
                return True
            same_flag = True

        return False

    def _is_fully_collapsed(self):
        """
        Check if all waves are collapsed.
        """
        for y in range(len(self._coefficient)):
            for x in range(len(self._coefficient[0])):
                if self._coefficient[y][x]:
                    return False
        return True

    def _iterate(self): # OK
        coords = self._get_min_entropy_coords()
        self._collapse_at(coords)
        self._propagate(coords)

    def _get_min_entropy_coords(self):
        """
        Return coordinates where the wave has minimum entropy(the minimum number of possible patterns) within uncollapsed waves.
        If two or more waves have the same minimum entropy, then return randomly out of the waves which have minimum entropy.
        """
        waves = self._waves
        min = sys.maxsize
        minCoords = [] # list of coords

        for col in range(len(waves)):
            for row in range(len(waves[0])):
                if self._coefficient[col][row]:
                    if waves[col][row].get_entropy() < min:
                        min = waves[col][row].get_entropy()
                        minCoords = [(col, row)]
                    elif waves[col][row].get_entropy() == min:
                        minCoords.append((col, row))

        # random choice
        index = random.randrange(len(minCoords))
        resultCoords = minCoords[index]

        return resultCoords

    def _collapse_at(self, coords):
        """
        Collapse a wave.
        """
        self._coefficient[coords[0]][coords[1]] = False
        wave = self._waves[coords[0]][coords[1]]
        # Choose one pattern randomly in a wave(will use weight)
        index = random.randrange(len(wave.patterns_uid))
        pattern_uid = [wave.patterns_uid[index]]
        wave.patterns_uid = pattern_uid

        print("Collapsed wave: " + str(coords[0]) + ", " + str(coords[1]))

    def _propagate(self, coords): #OK
        stack = [coords]

        while len(stack) > 0:
            # pop
            cur_coords = stack[len(stack)-1]
            stack.remove(stack[len(stack)-1])

            for neighbour_cell in self._get_neighboring_cells(cur_coords):
                vec = (neighbour_cell[0]-cur_coords[0], neighbour_cell[1]-cur_coords[1])
                possible_neighbours_uid = self._get_possible_neighbours_uid(cur_coords, vec)
                possible_patterns_uid = copy.copy(self._get_possible_patterns_uid(neighbour_cell))
                for possible_pattern_uid in possible_patterns_uid:
                    if not possible_pattern_uid in possible_neighbours_uid:
                        self._constrain(neighbour_cell, possible_pattern_uid)
                        if not neighbour_cell in stack:
                            stack.append(neighbour_cell)



    def _get_neighboring_cells(self, coords:tuple): # OK
        """
        Return valid neighboring cells.
        """
        t1 = time.time()

        direction = [(1, 0), (0, 1), (0, -1), (-1, 0)]
        if self._diagnal_check:
            direction += [(-1, 1), (-1, -1), (1, 1), (1, -1)]
        result_cell = []
        for d in direction:
            neighbour = (d[0]+coords[0], d[1]+coords[1])
            if self._is_valid_cell(neighbour):# and self._coefficient[neighbour[0]][neighbour[1]]:
                result_cell.append(neighbour)

        t2 = time.time()
        self.execution_t[self._get_neighboring_cells.__name__] += t2-t1
        self.execution_n[self._get_neighboring_cells.__name__] += 1

        return result_cell

    def _is_valid_cell(self, coords:tuple): #OK
        """
        Check if given coordinates are out of range on output cells.
        """
        if coords[0] < 0 or coords[1] < 0 or coords[0] > len(self._waves)-1 or coords[1] > len(self._waves[0])-1:
            return False
        else:
             return True

    def _get_possible_patterns_uid(self, coords:tuple):
        return self._waves[coords[0]][coords[1]].patterns_uid

    def _get_possible_neighbours_uid(self, coords:tuple, vec:tuple):
        """
        Return the patterns that can be placed along with this cell.
        Note that vec is (y, x) tuple, not (x, y).
        """
        t1 = time.time()

        possible_neighbours_uid = []

        # get center patterns
        center_patterns_uid = self._get_possible_patterns_uid(coords)

        # gather possible neighbour patterns
        for center_pattern_uid in center_patterns_uid:
            """
            for other_pattern_uid in self._patterns.keys():
                if self.index.check(center_pattern_uid, vec, other_pattern_uid):
                    possible_neighbours_uid.append(other_pattern_uid)"""
            possible_neighbours_uid.extend(self.neighbour_data[center_pattern_uid][vec])

        t2 = time.time()
        self.execution_t[self._get_possible_neighbours_uid.__name__] += t2-t1
        self.execution_n[self._get_possible_neighbours_uid.__name__] += 1

        return possible_neighbours_uid

    def _is_match_pattern(self, center_pattern:Pattern, dir_vec:tuple, other_pattern:Pattern): # OK
        """
        Check if 'other_pattern' can be placed at 'dir_vec' direction of 'center_pattern'.
        Note that vec is (y, x) tuple, not (x, y).
        """
        t1 = time.time()

        extract_size = self._extract_size
        dirs = self._vec2dir(dir_vec, extract_size)
        counter_dir = self._vec2dir((-dir_vec[0], -dir_vec[1]), extract_size)

        adj_pixels = center_pattern.adjacency_pixels
        target_pixels = self._2dim_pixels(other_pattern.pixels, extract_size)

        for _ in range(2):
            if dirs[0] == 'ul':
                if not adj_pixels['ul'].get_pixel() == target_pixels[extract_size[0]-1][extract_size[1]-1].get_pixel():
                    return False
            elif dirs[0] == 'ur':
                if not adj_pixels['ur'].get_pixel() == target_pixels[extract_size[0]-1][0].get_pixel():
                    return False
            elif dirs[0] == 'dl':
                if not adj_pixels['dl'].get_pixel() == target_pixels[0][extract_size[1]-1].get_pixel():
                    return False
            elif dirs[0] == 'dr':
                if not adj_pixels['dr'].get_pixel() == target_pixels[0][0].get_pixel():
                    return False
            elif dirs[0][0] == 'u':
                for i in range(extract_size[1]):
                    if not adj_pixels['u' + str(i)].get_pixel() == target_pixels[extract_size[0]-1][i].get_pixel():
                        return False
            elif dirs[0][0] == 'd':
                for i in range(extract_size[1]):
                    if not adj_pixels['d' + str(i)].get_pixel() == target_pixels[0][i].get_pixel():
                        return False
            elif dirs[0][0] == 'l':
                for i in range(extract_size[0]):
                    if not adj_pixels['l' + str(i)].get_pixel() == target_pixels[i][extract_size[1]-1].get_pixel():
                        return False
            elif dirs[0][0] == 'r':
                for i in range(extract_size[0]):
                    if not adj_pixels['r' + str(i)].get_pixel() == target_pixels[i][0].get_pixel():
                        return False
            # reverse
            dirs = counter_dir
            adj_pixels = other_pattern.adjacency_pixels
            target_pixels = self._2dim_pixels(center_pattern.pixels, extract_size)

        t2 = time.time()
        self.execution_t[self._is_match_pattern.__name__] += t2-t1
        self.execution_n[self._is_match_pattern.__name__] += 1

        return True
    
    def _vec2dir(self, vec, extract_size:tuple): # OK
        """
        Convert vec to the keys used in pattern dictionary.
        """
        t1 = time.time()

        dirs = []
        if vec[0] > 0:
            if vec[1] > 0:
                dirs.append('ur')
            elif vec[1] < 0:
                dirs.append('ul')
            elif vec[1] == 0:
                dirs = ['u' + str(i) for i in range(extract_size[1])]
        elif vec[0] < 0:
            if vec[1] > 0:
                dirs.append('dr')
            elif vec[1] < 0:
                dirs.append('dl')
            elif vec[1] == 0:
                dirs = ['d' + str(i) for i in range(extract_size[1])]
        elif vec [0] == 0:
            if vec[1] > 0:
                dirs = ['r' + str(i) for i in range(extract_size[0])]
            elif vec[1] < 0:
                dirs = ['l' + str(i) for i in range(extract_size[0])]
            elif vec[1] == 0:
                print("Something is wrong(_vec2dir)")
                dirs = ''

        t2 = time.time()
        self.execution_t[self._vec2dir.__name__] += t2-t1
        self.execution_n[self._vec2dir.__name__] += 1

        return dirs

    def _2dim_pixels(self, pixels:list, extract_size:tuple):
        """
        Convert a list of pixels to 2-dimentional array.
        """
        t1 = time.time()

        result = [pixels[i: i+extract_size[1]] for i in range(0, len(pixels), extract_size[1])]

        t2 = time.time()
        self.execution_t[self._2dim_pixels.__name__] += t2-t1
        self.execution_n[self._2dim_pixels.__name__] += 1

        return result

    def _constrain(self, coords:tuple, pattern_uid:uuid.UUID):
        """
        Remove a pattern from the wave.
        """
        wave = self._waves[coords[0]][coords[1]]
        wave.patterns_uid.remove(pattern_uid)

        if wave.get_entropy() == 0:
            print("Contradiction?: " + str(coords[0]) + ", " + str(coords[1]))
            self._get_result_img().show()
            exit()

    def _get_result_img(self):
        img = Image.new('RGBA', self._output_size)
        waves = self._waves
        extract_size = self._extract_size
        
        for col in range(len(waves)):
            for row in range(len(waves[0])):
                pixels = []
                if self._coefficient[col][row] == True: # this is for testing output
                    for _ in range(extract_size[1]):
                        for _ in range(extract_size[0]):
                            pixels.append(Pixel((0,255,0,255)))
                elif len(waves[col][row].patterns_uid) == 0:
                    for _ in range(extract_size[1]):
                        for _ in range(extract_size[0]):
                            pixels.append(Pixel((0,255,255,255)))
                else :
                    pixels = self._patterns[waves[col][row].patterns_uid[0]].pixels

                for pattern_col in range(extract_size[0]):
                    for pattern_row in range(extract_size[1]):
                        (x, y) = (col*extract_size[0]+pattern_col, row*extract_size[1]+pattern_row)
                        (r, g, b, a) = pixels[pattern_col*(extract_size[1]) + pattern_row].get_pixel()
                        img.putpixel((x, y), (r, g, b, a))

        return img

    def get_pattern_img(self, pattern:Pattern):
        """
        Return pattern image with adjacent pixels.
        """
        if isinstance(pattern, uuid.UUID):
            pattern = self._patterns[pattern]

        extract_size = self._extract_size
        img = Image.new('RGBA', (extract_size[1]+2, extract_size[0]+2))

        # 4 corners
        img.putpixel((0, 0), pattern.adjacency_pixels['ul'].get_pixel())
        img.putpixel((extract_size[1]+1, 0), pattern.adjacency_pixels['ur'].get_pixel())
        img.putpixel((0, extract_size[0]+1), pattern.adjacency_pixels['dl'].get_pixel())
        img.putpixel((extract_size[1]+1, extract_size[0]+1), pattern.adjacency_pixels['dr'].get_pixel())

        # other adjacency
        for x in range(1, 1+extract_size[1]):
            key = 'u' + str(x-1)
            img.putpixel((x, 0), pattern.adjacency_pixels[key].get_pixel())
            key = 'd' + str(x-1)
            img.putpixel((x, extract_size[0]+1), pattern.adjacency_pixels[key].get_pixel())
        for y in range(1, 1+extract_size[0]):
            key = 'l' + str(y-1)
            img.putpixel((0, y), pattern.adjacency_pixels[key].get_pixel())
            key = 'r' + str(y-1)
            img.putpixel((extract_size[1]+1, y), pattern.adjacency_pixels[key].get_pixel())

        # center
        i=0
        for y in range(1, 1+extract_size[0]):
            for x in range(1, 1+extract_size[1]):
                img.putpixel((x, y), pattern.pixels[i].get_pixel())
                i+=1

        return img

    def merge_images(self, images:list): # OK
        """
        Merge images into one big image and return.
        """
        height = 0
        width = 0
        for image in images:
            width += image.width + 1
            if height < image.height: # take max height as output height
                height = image.height

        result_image = Image.new('RGBA', (width, height))

        for i in range(len(images)):
            result_image.paste(images[i], (i*images[i].width+i, 0))


        return result_image

    def output_execution_analysis(self):
        """
        For debugging.
        """
        print("-----------Execution time-----------")
        for exe_time_key in self.execution_t.keys():
            log = exe_time_key + ": " + str(self.execution_t[exe_time_key])
            log += " (" + str(100*self.execution_t[exe_time_key]/self.execution_t['total']) + "%)"
            print(log)
        
        print("\n-----------Number of times called-----------")
        for exe_count_key in self.execution_n.keys():
            log = exe_count_key + ": " + str(self.execution_n[exe_count_key])
            print(log)

    def output_progress(self, progress:float):
        """
        Output progress bar like [===>      ] 30%
        progress must be between 0 to 1
        """
        progress_bar = ""
        for i in range(int(progress*10)):
            progress_bar += '='
        progress_bar += '>'
        while len(progress_bar) <= 10:
            progress_bar += ' '

        progress_str = "[" + progress_bar + "] " + str(int(progress*100)) + "%"

        sys.stderr.write('\r\033[K' + progress_str)
        sys.stderr.flush()


# wfc = WFC("./image/switch.png", (1,1), (16, 16), rotate=True, diagnal_check=True)
# wfc.do_magic()
