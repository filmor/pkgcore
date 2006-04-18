# Copyright: 2006 Brian Harring <ferringb@gmail.com>
# License: GPL2

from pkgcore.restrictions import packages, values, boolean
from pkgcore.util.iterables import expandable_chain, caching_iter
from pkgcore.util.compatibility import all, any
from pkgcore.graph.choice_point import choice_point
from pkgcore.util.lists import iter_flatten


debug_whitelist = [None, "unsatisfy", "ref", "blockers"]
def debug(msg, id=None):
	if id in debug_whitelist:
		print "debug: %s" % msg


class NoSolution(Exception):
	def __init__(self, msg):
		self.msg = msg
	def __str__(self):
		return str(msg)


class resolver(object):

	def __init__(self):
		self.search_stacks = [[]]
		self.grab_next_stack()
		self.current_atom = None
		self.false_atoms = set()
		self.atoms = {}
		self.pkg_atoms = {}

	def add_root_atom(self, atom):
		if atom in self.atoms:
			# register a root level stack
			self.ref_stack_for_atom(h, [])
		else:
			self.search_stacks.append([atom])
			self.grab_next_stack()

	def grab_next_stack(self):
		self.current_stack = self.search_stacks[-1]

	def iterate_unresolved_atoms(self):
		while self.search_stacks:
			assert self.current_stack is self.search_stacks[-1]
			if not self.current_stack:
				self.search_stacks.pop(-1)
				if not self.search_stacks:
					self.current_stack = None
					return
				self.grab_next_stack()
				continue
			try:
				assert not any(x.blocks for x in self.current_stack)
			except AssertionError:
				import pdb;pdb.set_trace()
				raise				

			debug("stack is %s" % self.current_stack)
			a = self.current_stack[-1]
			missing_atoms = False
			if a not in self.atoms:
				debug("  1: missing atom: %s" % a)
				missing_atoms = True
			else:
				c = self.atoms[a][0]
				t = tuple(self.current_stack)
				missing_atoms = False
				for x in c.depends + c.rdepends:
					# yes that was innefficient
					if x not in self.atoms:
						self.current_atom = x
						self.current_stack.append(x)
						missing_atoms = True
						break
					else:
						#ensure we're registered.
						self.ref_stack_for_atom(x, t)
		
			if missing_atoms:
				debug("  2: missing_atoms for %s: %s" % (a, self.current_stack[-1]))
				# cycle protection.
				self.current_atom = self.current_stack[-1]
				
				if self.current_atom in self.current_stack[:-1]:
					# cycle ask the repo for a pkg configuration that breaks the cycle.
					debug("   cycle detected for %s: stack %s" % (a, self.current_stack))
					v = values.ContainmentMatch(a, negate=True)
					yield packages.AndRestriction(self.current_atom, 
						packages.PackageRestriction("depends", v), packages.PackageRestriction("rdepends", v))
				elif a.blocks:
					import pdb;pdb.set_trace()
					backup = False
					for x in self.pkg_atoms.get(a.key, []):
						if not x:
							# huh.  this shouldn't exist most likely.
							print "!!! %s exists in graph but isn't valid" % (x.atom)
						elif a.match(x.current_pkg):
							debug("  checking blocker %s, found %s (from %s)" % (a, x.current_pkg, x.atom))
							self.current_atom = a
							cur = self.current_stack
							self.unsatisfiable_atom(a, "backtracking for blocker", False)
							cur.pop(-1)
							backup = True
							break
					else:
						print "me3"
						# ref it.
						self.atoms[a] = [choice_point(a, []), []]
						self.ref_stack_for_atom(a, t)
						self.current_stack.pop(-1)
				else:
					debug("   yielding %s for %s" % (a, self.current_stack))
					yield self.current_atom
			else:
				# all satisfied.
				self.current_stack.pop(-1)

			try:
				assert not any(x.blocks for x in self.current_stack)
			except AssertionError:
				import pdb;pdb.set_trace()
				raise				

	
	def satisfy_atom(self, atom, matches):
		assert atom is self.current_stack[-1]
		c = choice_point(atom, caching_iter(matches))
		self.atoms[atom] = [c, []]
		self.pkg_atoms.setdefault(atom.key, []).append(c)
		# is this right?
		self.ref_stack_for_atom(atom, self.current_stack)
		if not c:
			debug("  results for %s was empty" % (atom))
			cur = self.current_stack
			self.unsatisfiable_atom(atom)
			if cur is self.current_stack:
				self.current_stack.pop(-1)
		else:
			debug("  results for %s was %s" % (atom, c))
		
		debug("  satisfy_atoms exiting: stack %s" % (self.search_stacks), "satisfy")
		debug("  satisfy_atoms exiting: atoms %s" % str(self.atoms.keys()), "satisfy")
		
	def unsatisfiable_atom(self, atom, msg="None supplied", permenant=True):
		# what's on the stack may be different from current_atom; union of atoms will do this fex.
		assert atom is self.current_atom
		a = self.current_atom

		if permenant:
			# register this as unsolvable
			self.false_atoms.add(atom)

		bail = None
		istack = expandable_chain(self.atoms[atom][1])
		for stack in istack:
			if not stack:
				# this is a root atom, eg externally supplied. Continue cleanup, but raise.
				debug("    caught a root node, setting bail for %s" % (atom))
				bail = NoSolution("root node %s was marked unsatisfiable, reason: %s" % (atom, msg))

			c = self.atoms[stack[-2]][0]
			try:
				was_complete = self.choice_point_is_complete(c)
				released_atoms, released_provides = c.reduce_atoms(stack[-1])
			except IndexError:
				was_complete = False
				# bug
				released_atoms, released_provides = (stack[-1],), []
			t = tuple(stack[:-1])
			debug("    released_atoms for %s == %s" % (stack, released_atoms), "unsatisfy")
			for x in (x for x in released_atoms if x in self.atoms):
				# how's this work for external specified root atoms?
				# could save 'em also; need a queue with faster then O(N) lookup for it though.
				print x
				self.deref_stack_for_atom(x, t)

			if not c:
				# notify the parents.
				# this work properly? :)
				istack.append([t])
			elif was_complete and not self.choice_point_is_complete(c):
				# if we've made it incomplete, well, time to go anew at it.
				self.search_stacks.append(list(t))

		self.grab_next_stack()
		if bail is not None:
			raise bail
		new_stack = []
		debug("    exiting unsatisfiable: atoms %s" % self.atoms, "unsatisfy")
		debug("    exiting unsatisfiable: stacks %s" % self.search_stacks, "unsatisfy")

	def choice_point_is_complete(self, choice_point):
		return all(x in self.atoms for x in choice_point.depends) and \
			all(x in self.atoms for x in choice_point.rdepends)

	def ref_stack_for_atom(self, atom, stack):
		assert atom in self.atoms
		if not isinstance(stack, tuple):
			stack = tuple(stack)
		if stack not in self.atoms[atom][1]:
			self.atoms[atom][1].append(stack)

	def deref_stack_for_atom(self, atom, stack):
		try:
			assert atom in self.atoms
		except AssertionError:
			debug("      atoms is %s, stack was %s" % (atom, stack))
			raise
		if not isinstance(stack, tuple):
			stack = tuple(stack)
		stack_l = len(stack)
		l = [x for x in self.atoms[atom][1] if x[:stack_l] != stack]
		if l:
			self.atoms[atom][1] = l
			debug("  deref: atom %s, derefed stack %s" % (atom, stack), "ref")
		else:
			debug("  deref: released %s" % atom, "ref")
			if atom.key in self.pkg_atoms:
				l = [x for x in self.pkg_atoms[atom.key] if atom != x.atom]
				if not l:
					del self.pkg_atoms[atom.key]
				else:
					self.pkg_atoms[atom.key] = l
			del self.atoms[atom]
			
