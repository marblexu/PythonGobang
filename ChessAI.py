from GameMap import *
from enum import IntEnum
from random import randint
import copy
import time

AI_SEARCH_DEPTH = 4
AI_LIMITED_MOVE_NUM = 20

DEBUG_LEVEL = 2

DEBUG_NONE = 0
DEBUG_ERROR = 1
DEBUG_WARN = 2
DEBUG_INFO = 3

def DEBUG(LEVEL, *args):
	if DEBUG_LEVEL >= LEVEL:
		len_args = range(len(args))
		for Index in len_args:
			print(args[Index])


class CHESS_TYPE(IntEnum):
	NONE = 0,
	SLEEP_TWO = 1,
	LIVE_TWO = 2,
	SLEEP_THREE = 3
	LIVE_THREE = 4,
	CHONG_FOUR = 5,
	LIVE_FOUR = 6,
	LIVE_FIVE = 7,
	
CHESS_TYPE_NUM = 8

FIVE = CHESS_TYPE.LIVE_FIVE.value
FOUR, THREE, TWO = CHESS_TYPE.LIVE_FOUR.value, CHESS_TYPE.LIVE_THREE.value, CHESS_TYPE.LIVE_TWO.value
SFOUR, STHREE, STWO = CHESS_TYPE.CHONG_FOUR.value, CHESS_TYPE.SLEEP_THREE.value, CHESS_TYPE.SLEEP_TWO.value

SCORE_MAX = 0x7fffffff
SCORE_MIN = -1 * SCORE_MAX
SCORE_FIVE = 10000

class ZobristHash():
	def __init__(self, chess_len):
		self.max = 2**32
		self.player1 = [[self.getRandom() for x in range(chess_len)] for y in range(chess_len)]
		self.player2 = [[self.getRandom() for x in range(chess_len)] for y in range(chess_len)]
		self.data = [self.player1, self.player2]
		self.code = self.getRandom()
		self.cache = {}

	def getRandom(self):
		return randint(1, self.max)
	
	def generate(self, index, x, y):
		self.code = self.code ^ self.data[index][y][x]
	
	def resetCache(self):
		self.cache = {}

	def getCache(self):	
		if self.code in self.cache:
			return self.cache[self.code]
		else:
			return None
	
	def setCache(self, depth, score):
		DEBUG(DEBUG_INFO, 'code[%d], depth[%d], score[%d]' % (self.code, depth, score))
		self.cache[self.code] = (depth, score)

class ChessAI():
	def __init__(self, chess_len, cache=True):
		self.len = chess_len
		# [horizon, vertical, left diagonal, right diagonal]
		self.record = [[[0,0,0,0] for x in range(chess_len)] for y in range(chess_len)]
		self.count = [[0 for x in range(CHESS_TYPE_NUM)] for i in range(2)]
		self.pos_score = [[(7 - max(abs(x - 7), abs(y - 7))) for x in range(chess_len)] for y in range(chess_len)]
		self.cache = cache
		self.cacheGet = 0
		if self.cache:
			self.zobrist = ZobristHash(chess_len)
		
	def reset(self):
		for y in range(self.len):
			for x in range(self.len):
				for i in range(4):
					self.record[y][x][i] = 0

		for i in range(len(self.count)):
			for j in range(len(self.count[0])):
				self.count[i][j] = 0
		
		self.save_count = 0
	
	def click(self, map, x, y, turn):
		map.click(x, y, turn)
		if self.cache:
			self.zobrist.generate(turn.value - 1, x, y)

	def set(self, board, x, y, turn):
		board[y][x] = turn.value
		if self.cache:
			self.zobrist.generate(turn.value - 1, x, y)
	
	def remove(self, board, x, y, turn):
		board[y][x] = 0
		if self.cache:
			self.zobrist.generate(turn.value - 1, x, y)
		
	def isWin(self, board, turn):
		return self.__evaluate(board, turn, True)
	
	# get all positions that is empty
	def genmove(self, board, turn):
		moves = []
		for y in range(self.len):
			for x in range(self.len):
				if board[y][x] == 0:
					score = self.pos_score[y][x]
					moves.append((score, x, y))

		moves.sort(reverse=True)
		return moves
	
	# evaluate score of point, to improve pruning efficiency
	def evaluatePointScore(self, board, x, y, mine, opponent):
		dir_offset = [(1, 0), (0, 1), (1, 1), (1, -1)] # direction from left to right
		for i in range(len(self.count)):
			for j in range(len(self.count[0])):
				self.count[i][j] = 0
				
		board[y][x] = mine
		self.evaluatePoint(board, x, y, mine, opponent, self.count[mine-1])
		mine_count = self.count[mine-1]
		board[y][x] = opponent
		self.evaluatePoint(board, x, y, opponent, mine, self.count[opponent-1])
		opponent_count = self.count[opponent-1]
		
		mscore, oscore = self.getScore(mine_count, opponent_count)
		if mscore >= SCORE_FIVE or oscore >= SCORE_FIVE:
			DEBUG(DEBUG_INFO, '(%d, %d), %d:%d, %d:%d' % (x, y, mine-1, mscore, opponent-1, oscore))
		return max(mscore, oscore)
				
	# get all positions near chess
	def genmove1(self, board, turn):
		def addMove(self, board, moves, x, y, mine, opponent):
			if x >= 0 and x < self.len and y >= 0 and y < self.len:
				if board[y][x] == 0:
					#score = self.pos_score[y][x]
					score = self.evaluatePointScore(board, x, y, mine, opponent)
					moves.append((score, x, y))
					board[y][x] = 3
		
		if turn == MAP_ENTRY_TYPE.MAP_PLAYER_ONE:
			mine = 1
			opponent = 2
		else:
			mine = 2
			opponent = 1

		moves = []
		for y in range(self.len):
			for x in range(self.len):
				if board[y][x] != 0 and board[y][x] != 3:
					offset = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
					for i in range(len(offset)):
						addMove(self, board, moves, x + offset[i][0], y + offset[i][1], mine, opponent)

		moves.sort(reverse=True)
		for y in range(self.len):
			for x in range(self.len):
				if board[y][x] == 3:
					board[y][x] = 0
		DEBUG(DEBUG_INFO, 'len:', len(moves), '  ', moves)

		# FIXME: decrease think time: only consider limited moves with higher score
		if self.maxdepth > 2 and len(moves) > AI_LIMITED_MOVE_NUM:
			moves = moves[:AI_LIMITED_MOVE_NUM]
		return moves
	
	def __search(self, board, turn, depth, alpha = SCORE_MIN, beta = SCORE_MAX):
		score = self.evaluate(board, turn, self.maxdepth - depth)
		if depth <= 0 or abs(score) >= SCORE_FIVE: 
			return score

		moves = self.genmove1(board, turn)
		bestmove = None
		self.alpha += len(moves)

		for score, x, y in moves:
			self.set(board, x, y, turn)
			
			if turn == MAP_ENTRY_TYPE.MAP_PLAYER_ONE:
				op_turn = MAP_ENTRY_TYPE.MAP_PLAYER_TWO
			else:
				op_turn = MAP_ENTRY_TYPE.MAP_PLAYER_ONE

			score = - self.__search(board, op_turn, depth - 1, -beta, -alpha)

			self.remove(board, x, y, turn)
			self.belta += 1

			# alpha/beta pruning
			if score > alpha:
				alpha = score
				bestmove = (x, y)
				if alpha >= beta:
					break

		if depth == self.maxdepth and bestmove:
			self.bestmove = bestmove
		
		if self.cache and bestmove and abs(alpha) <= SCORE_FIVE:
			self.zobrist.setCache(self.maxdepth - depth, alpha)
				
		return alpha

	def search(self, board, turn, depth = 4):
		for i in range(2, depth+1, 2):
			self.maxdepth = i
			self.bestmove = None
			self.zobrist.resetCache()
			score = self.__search(board, turn, i)
			if abs(score) >= SCORE_FIVE:
				DEBUG(DEBUG_WARN, i, score)
				break

		x, y = self.bestmove
		return score, x, y
		
	def findBestChess(self, board, turn):
		time1 = time.time()
		self.alpha = 0
		self.belta = 0
		score, x, y = self.search(board, turn, AI_SEARCH_DEPTH)
		time2 = time.time()
		DEBUG(DEBUG_WARN, 'time[%.2f] (%d, %d), score[%d] alpha[%d] belta[%d] save[%d] cache[%d]' % ((time2-time1), x, y, score, self.alpha, self.belta, self.save_count, self.cacheGet))
		return (x, y)
		
	def evaluate(self, board, turn, depth):
		if self.cache:
			c = self.zobrist.getCache()
			if c is not None and c[0] >= depth:
				self.cacheGet += 1
				return c[1]
				
		score = self.__evaluate(board, turn)
		return score
	
	# calculate score, FIXME: May Be Improved
	def getScore(self, mine_count, opponent_count):
		mscore, oscore = 0, 0
		if mine_count[FIVE] > 0:
			return (0, SCORE_FIVE)
		if opponent_count[FIVE] > 0:
			return (0, SCORE_FIVE)
				
		if mine_count[SFOUR] >= 2:
			mine_count[FOUR] += 1
		if opponent_count[SFOUR] >= 2:
			opponent_count[FOUR] += 1
				
		if mine_count[FOUR] > 0:
			return (9050, 0)
		if mine_count[SFOUR] > 0:
			return (9040, 0)
			
		if opponent_count[FOUR] > 0:
			return (0, 9030)
		if opponent_count[SFOUR] > 0 and opponent_count[THREE] > 0:
			return (0, 9020)
			
		if mine_count[THREE] > 0 and opponent_count[SFOUR] == 0:
			return (9010, 0)
			
		if (opponent_count[THREE] > 1 and mine_count[THREE] == 0 and mine_count[STHREE] == 0):
			return (0, 9000)

		if opponent_count[SFOUR] > 0:
			oscore += 400

		if mine_count[THREE] > 1:
			mscore += 500
		elif mine_count[THREE] > 0:
			mscore += 100
			
		if opponent_count[THREE] > 1:
			oscore += 2000
		elif opponent_count[THREE] > 0:
			oscore += 400

		if mine_count[STHREE] > 0:
			mscore += mine_count[STHREE] * 10
		if opponent_count[STHREE] > 0:
			oscore += opponent_count[STHREE] * 10
			
		if mine_count[TWO] > 0:
			mscore += mine_count[TWO] * 4
		if opponent_count[TWO] > 0:
			oscore += opponent_count[TWO] * 4
				
		if mine_count[STWO] > 0:
			mscore += mine_count[STWO] * 4
		if opponent_count[STWO] > 0:
			oscore += opponent_count[STWO] * 4
		
		return (mscore, oscore)

	def __evaluate(self, board, turn, checkWin=False):
		self.reset()
		
		if turn == MAP_ENTRY_TYPE.MAP_PLAYER_ONE:
			mine = 1
			opponent = 2
		else:
			mine = 2
			opponent = 1
		
		for y in range(self.len):
			for x in range(self.len):
				if board[y][x] == mine:
					self.evaluatePoint(board, x, y, mine, opponent)
				elif board[y][x] == opponent:
					self.evaluatePoint(board, x, y, opponent, mine)
		
		mine_count = self.count[mine-1]
		opponent_count = self.count[opponent-1]
		if checkWin:
			DEBUG(DEBUG_WARN, '%d: %s\n%d: %s' % (mine-1, mine_count, opponent-1, opponent_count))
			return mine_count[FIVE] > 0
		else:	
			mscore, oscore = self.getScore(mine_count, opponent_count)
			return (mscore - oscore)
	
	def evaluatePoint(self, board, x, y, mine, opponent, count=None):
		dir_offset = [(1, 0), (0, 1), (1, 1), (1, -1)] # direction from left to right
		ignore_record = True
		if count is None:
			count = self.count[mine-1]
			ignore_record = False
		for i in range(4):
			if self.record[y][x][i] == 0 or ignore_record:
				self.analysisLine1(board, x, y, i, dir_offset[i], mine, opponent, count)
				#type = self.analysisLine(board, x, y, i, dir_offset[i], mine, opponent)
				#if type != CHESS_TYPE.NONE:
				#	self.count[mine-1][type.value] += 1
			else:
				self.save_count += 1
	
	# line is fixed len 9: XXXXMXXXX
	def getLine(self, board, x, y, dir_offset, mine, opponent):
		line = [0 for i in range(9)]
		
		tmp_x = x + (-5 * dir_offset[0])
		tmp_y = y + (-5 * dir_offset[1])
		for i in range(9):
			tmp_x += dir_offset[0]
			tmp_y += dir_offset[1]
			if (tmp_x < 0 or tmp_x >= self.len or 
				tmp_y < 0 or tmp_y >= self.len):
				line[i] = opponent # set out of range as opponent chess
			else:
				line[i] = board[tmp_y][tmp_x]
						
		return line
		
	def analysisLine1(self, board, x, y, dir_index, dir, mine, opponent, count):
		# record line range[left, right] as analysized
		def setRecord(self, x, y, left, right, dir_index, dir_offset):
			tmp_x = x + (-5 + left) * dir_offset[0]
			tmp_y = y + (-5 + left) * dir_offset[1]
			for i in range(left, right+1):
				tmp_x += dir_offset[0]
				tmp_y += dir_offset[1]
				self.record[tmp_y][tmp_x][dir_index] = 1
	
		empty = MAP_ENTRY_TYPE.MAP_EMPTY.value
		left_idx, right_idx = 4, 4
		
		line = self.getLine(board, x, y, dir, mine, opponent)

		while right_idx < 8:
			if line[right_idx+1] != mine:
				break
			right_idx += 1
		while left_idx > 0:
			if line[left_idx-1] != mine:
				break
			left_idx -= 1
		
		left_range, right_range = left_idx, right_idx
		while right_range < 8:
			if line[right_range+1] == opponent:
				break
			right_range += 1
		while left_range > 0:
			if line[left_range-1] == opponent:
				break
			left_range -= 1
		
		chess_range = right_range - left_range + 1
		if chess_range < 5:
			setRecord(self, x, y, left_range, right_range, dir_index, dir)
			return CHESS_TYPE.NONE
		
		setRecord(self, x, y, left_idx, right_idx, dir_index, dir)
		
		m_range = right_idx - left_idx + 1
		
		# M:mine chess, P:opponent chess or out of range, X: empty
		if m_range == 5:
			count[FIVE] += 1
		
		# Live Four : XMMMMX 
		# Chong Four : XMMMMP, PMMMMX
		if m_range == 4:
			left_empty = right_empty = False
			if line[left_idx-1] == empty:
				left_empty = True			
			if line[right_idx+1] == empty:
				right_empty = True
			if left_empty and right_empty:
				count[FOUR] += 1
			elif left_empty or right_empty:
				count[SFOUR] += 1
		
		# Chong Four : MXMMM, MMMXM, the two types can both exist
		# Live Three : XMMMXX, XXMMMX
		# Sleep Three : PMMMX, XMMMP, PXMMMXP
		if m_range == 3:
			left_empty = right_empty = False
			left_four = right_four = False
			if line[left_idx-1] == empty:
				if line[left_idx-2] == mine: # MXMMM
					setRecord(self, x, y, left_idx-2, left_idx-1, dir_index, dir)
					count[SFOUR] += 1
					left_four = True
				left_empty = True
				
			if line[right_idx+1] == empty:
				if line[right_idx+2] == mine: # MMMXM
					setRecord(self, x, y, right_idx+1, right_idx+2, dir_index, dir)
					count[SFOUR] += 1
					right_four = True 
				right_empty = True
			
			if left_four or right_four:
				pass
			elif left_empty and right_empty:
				if chess_range > 5: # XMMMXX, XXMMMX
					count[THREE] += 1
				else: # PXMMMXP
					count[STHREE] += 1
			elif left_empty or right_empty: # PMMMX, XMMMP
				count[STHREE] += 1
		
		# Chong Four: MMXMM, only check right direction
		# Live Three: XMXMMX, XMMXMX the two types can both exist
		# Sleep Three: PMXMMX, XMXMMP, PMMXMX, XMMXMP
		# Live Two: XMMX
		# Sleep Two: PMMX, XMMP
		if m_range == 2:
			left_empty = right_empty = False
			left_three = right_three = False
			if line[left_idx-1] == empty:
				if line[left_idx-2] == mine:
					setRecord(self, x, y, left_idx-2, left_idx-1, dir_index, dir)
					if line[left_idx-3] == empty:
						if line[right_idx+1] == empty: # XMXMMX
							count[THREE] += 1
						else: # XMXMMP
							count[STHREE] += 1
						left_three = True
					elif line[left_idx-3] == opponent: # PMXMMX
						if line[right_idx+1] == empty:
							count[STHREE] += 1
							left_three = True
						
				left_empty = True
				
			if line[right_idx+1] == empty:
				if line[right_idx+2] == mine:
					if line[right_idx+3] == mine:  # MMXMM
						setRecord(self, x, y, right_idx+1, right_idx+2, dir_index, dir)
						count[SFOUR] += 1
						right_three = True
					elif line[right_idx+3] == empty:
						#setRecord(self, x, y, right_idx+1, right_idx+2, dir_index, dir)
						if left_empty:  # XMMXMX
							count[THREE] += 1
						else:  # PMMXMX
							count[STHREE] += 1
						right_three = True
					elif left_empty: # XMMXMP
						count[STHREE] += 1
						right_three = True
						
				right_empty = True
			
			if left_three or right_three:
				pass
			elif left_empty and right_empty: # XMMX
				count[TWO] += 1
			elif left_empty or right_empty: # PMMX, XMMP
				count[STWO] += 1
		
		# Live Two: XMXMX, XMXXMX only check right direction
		# Sleep Two: PMXMX, XMXMP
		if m_range == 1:
			left_empty = right_empty = False
			if line[left_idx-1] == empty:
				if line[left_idx-2] == mine:
					if line[left_idx-3] == empty:
						if line[right_idx+1] == opponent: # XMXMP
							count[STWO] += 1
				left_empty = True

			if line[right_idx+1] == empty:
				if line[right_idx+2] == mine:
					if line[right_idx+3] == empty:
						if left_empty: # XMXMX
							#setRecord(self, x, y, left_idx, right_idx+2, dir_index, dir)
							count[TWO] += 1
						else: # PMXMX
							count[STWO] += 1
				elif line[right_idx+2] == empty:
					if line[right_idx+3] == mine and line[right_idx+4] == empty: # XMXXMX
						count[TWO] += 1
						
		return CHESS_TYPE.NONE

    #================== below is another chess type checking way ==========================
	def checkType(self, board, x, y, dir_offset, type_dir, opponent):
		for (offset, expect_type) in type_dir.items():
			tmp_x = x + offset * dir_offset[0]
			tmp_y = y + offset * dir_offset[1]
			if (tmp_x < 0 or tmp_x >= self.len or 
				tmp_y < 0 or tmp_y >= self.len):
				pos_type = opponent # the effect of out of map range is as same as opponent
			else:
				pos_type = board[tmp_y][tmp_x]

			if pos_type != expect_type:
				return False
		return True
	
	def checTypeList(self, board, x, y, dir, type_list, opponent):
		for type_dir in type_list:
			if self.checkType(board, x, y, dir, type_dir, opponent):
				return True
		return False
	
	def recordVisited(self, board, x, y, dir_index, dir_offset, len):
		for i in range(len):
			tmp_x = x + i * dir_offset[0]
			tmp_y = y + i * dir_offset[1]
			self.record[tmp_y][tmp_x][dir_index] = 1

	def analysisLine(self, board, x, y, dir_index, dir, mine, opponent):
		empty = MAP_ENTRY_TYPE.MAP_EMPTY.value

		# Search turn from high priority to low priority
		# Live Five
		type_dir1 = {0:mine, 1:mine, 2:mine, 3:mine, 4:mine}
		type_list = [type_dir1]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 5)
			return CHESS_TYPE.LIVE_FIVE
		
		# Live Four
		type_dir1 = {-1:empty, 0:mine, 1:mine, 2:mine, 3:mine, 4:empty}
		type_list = [type_dir1]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 4)
			return CHESS_TYPE.LIVE_FOUR
				
		# Chong Four
		type_dir1 = {-1:opponent, 0:mine, 1:mine, 2:mine, 3:mine, 4:empty}
		type_dir2 = {-1:empty, 0:mine, 1:mine, 2:mine, 3:mine, 4:opponent}
		type_dir3 = {0:mine, 1:empty, 2:mine, 3:mine, 4:mine}
		type_dir4 = {0:mine, 1:mine, 2:empty, 3:mine, 4:mine}
		type_dir5 = {0:mine, 1:mine, 2:mine, 3:empty, 4:mine}
		type_list = [type_dir1, type_dir2, type_dir3, type_dir4, type_dir5]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 4)
			return CHESS_TYPE.CHONG_FOUR
				
		# Live Three
		type_dir1 = {-1:empty, 0:mine, 1:mine, 2:mine, 3:empty}
		type_dir2 = {-1:empty, 0:mine, 1:empty, 2:mine, 3:mine, 4:empty}
		type_dir3 = {-1:empty, 0:mine, 1:mine, 2:empty, 3:mine, 4:empty}
		type_list = [type_dir1, type_dir2, type_dir3]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 4)
			return CHESS_TYPE.LIVE_THREE
				
		# Sleep Three
		type_dir1 = {-1:opponent, 0:mine, 1:mine, 2:mine, 3:empty, 4:empty}
		type_dir2 = {-1:opponent, 0:mine, 1:empty, 2:mine, 3:mine, 4:empty}
		type_dir3 = {-1:opponent, 0:mine, 1:mine, 2:empty, 3:mine, 4:empty}
		type_dir4 = {0:mine, 1:mine, 2:empty, 3:empty, 4:mine}
		type_dir5 = {0:mine, 1:empty, 2:mine, 3:empty, 4:mine}
		type_dir6 = {0:mine, 1:empty, 2:empty, 3:mine, 4:mine}
		type_dir7 = {-2:empty, -1:empty, 0:mine, 1:mine, 2:mine, 3:opponent}
		type_dir8 = {-1:empty, 0:mine, 1:empty, 2:mine, 3:mine, 4:opponent}
		type_dir9 = {-1:empty, 0:mine, 1:mine, 2:empty, 3:mine, 4:opponent}
		type_dir10 = {-2:opponent,-1:empty, 0:mine, 1:mine, 2:mine, 3:empty, 4:opponent}
		
		type_list = [type_dir1, type_dir2, type_dir3, type_dir4, type_dir5, type_dir6, type_dir7, type_dir8, type_dir9, type_dir10]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 3)
			return CHESS_TYPE.SLEEP_THREE
		
		# Live Two
		type_dir1 = {-2:empty, -1:empty, 0:mine, 1:mine, 2:empty}
		type_dir2 = {-1:empty, 0:mine, 1:mine, 2:empty, 3:empty}
		type_dir3 = {-1:empty, 0:mine, 1:empty, 2:mine, 3:empty}
		type_dir4 = {-1:empty, 0:mine, 1:empty, 2:empty, 3:mine, 4:empty}
		type_list = [type_dir1, type_dir2, type_dir3, type_dir4]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 3)
			return CHESS_TYPE.LIVE_TWO
		
		# Sleep Two
		type_dir1 = {-1:opponent, 0:mine, 1:mine, 2:empty, 3:empty, 4:empty}
		type_dir2 = {-1:opponent, 0:mine, 1:empty, 2:mine, 3:empty, 4:empty}
		type_dir3 = {-1:opponent, 0:mine, 1:empty, 2:empty, 3:mine, 4:empty}
		type_dir3 = {-2:opponent, -1:empty, 0:mine, 1:mine, 2:empty, 3:empty}
		type_dir4 = {-3:empty, -2:empty, -1:empty, 0:mine, 1:mine, 2:opponent}
		type_dir5 = {-2:empty, -1:empty, 0:mine, 1:empty, 2:mine, 3:opponent}
		type_dir6 = {-1:empty, 0:mine, 1:empty, 2:empty, 3:mine, 4:opponent}
		type_list = [type_dir1, type_dir2, type_dir3, type_dir4, type_dir5, type_dir6]
		if self.checTypeList(board, x, y, dir, type_list, opponent):
			#self.recordVisited(board, x, y, dir_index, dir, 2)
			return CHESS_TYPE.SLEEP_TWO
		
		return CHESS_TYPE.NONE
		