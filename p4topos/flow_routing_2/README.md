# Flow Routing Topology with Multiple Paths of Equal Cost (Multi Pathing Scenario 2)
```
                         +----+
               +---------+ s2 +---------+
               |         +----+         |
               |                        |
               |         +----+         |
               |+--------+ s3 +--------+|
               ||        +----+        ||
               ||                      ||
+----+       +-++-+      +----+      +-++-+       +----+
| h1 +-------+ s1 +------+ s4 + -----+ s7 +-------+ h7 |
+----+       +-++-+      +----+      +-++-+       +----+
               ||                      ||
               ||        +----+        ||     
               |+--------+ s5 +--------+|            
               |         +----+         |
               |                        |
               |         +----+         |
               +---------+ s6 +---------+
                         +----+         
```