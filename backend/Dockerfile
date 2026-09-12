FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY pom.xml ./pom.xml
COPY backend/pom.xml ./backend/pom.xml
RUN mvn -pl backend -am dependency:go-offline
COPY backend/src ./backend/src
RUN mvn -pl backend -am package -DskipTests

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 mineguard
COPY --from=build /workspace/backend/target/mineguard-backend-*.jar /app/app.jar
USER 10001
EXPOSE 18080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
