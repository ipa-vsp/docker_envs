# Compatibility patches

Common `*.patch` files are applied to every distribution, followed by patches in
`branches/<branch>/`, then the distribution's subdirectory. Patches must apply
cleanly; failures stop builds.
The image and validation artifacts record the SHA256 of every applied patch.

`0001-example-test-targets.patch` fixes three upstream test fixture mismatches:
the namespaced test launched the non-namespaced example; the CiA402 test omitted
the configured `/test1` namespace; and the robot test published to the controller
name instead of its `/commands` topic. Assertions are retained. The independent
probes additionally assert actual PDO and position feedback.

`branches/master/0002-cmake-linkage.patch` makes both additional yaml-cpp link
declarations use `PUBLIC`, matching the existing declarations on those targets.
Without it CMake rejects `canopen_core` for mixing plain and keyword signatures.
This was reproduced in the Lyrical build; Humble uses different CMake code.

`creator/rolling-testing.patch` changes the Rolling creator's apt feed to
`ros2-testing`, which currently publishes Rolling desktop for Ubuntu 26.04;
the stable feed currently contains only Lyrical desktop for that OS. The base
helper applies this patch to a copy under `artifacts/rolling/`, leaving the
repository's creator unchanged. Its hash is recorded in `base-patches.txt`.
