package com.jiapeng.mineguard;

import org.junit.jupiter.api.Test;
import org.springframework.modulith.core.ApplicationModules;

class ArchitectureTest {

    @Test
    void moduleDependenciesRemainAcyclic() {
        ApplicationModules.of(MineGuardApplication.class).verify();
    }
}
