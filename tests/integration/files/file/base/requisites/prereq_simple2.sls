#
# Theory:
#
# C <--+ <--+ <-+ <-+
#      |    |   |   |
# A ---+    |   |   | # order of A/B/D/E is free
#           |   |   |
# B --------+   |   |
#               |   |
# D-------------+   |
#                   |
# E-----------------+

# B --------+----->(ouch, unrespected C prereq B)
#           |
# C <--+ <--+ <-+ <-+
#      |        |   |
# D ---+        |   |
#               |   |
# E-------------+   |
#                   |
# A-----------------+

# runs after C
A:
  cmd.run:
    - name: echo A
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - cmd: C

B:
  cmd.run:
    - name: echo B

# runs before D and B
C:
  cmd.run:
    - name: echo C
    # will test D and be applied only if D changes,
    # and then will run before D. Same for B
    - prereq:
      - cmd: B
      - cmd: D

D:
  cmd.run:
    - name: echo D

E:
  cmd.run:
    - name: echo E
    # is running in test mode before C
    # C gets executed first if this states modify something
    - prereq_in:
      - cmd: C
