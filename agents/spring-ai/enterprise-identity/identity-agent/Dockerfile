# Same shape as every other Java image in this repository: the jar is built by Maven first and the
# image only carries it. 21, not 11, because Spring Boot 4 requires it.
FROM amazoncorretto:21-alpine
EXPOSE 8006
ENV APP_PORT=8006
VOLUME /tmp
COPY target/*.jar app.jar
ENTRYPOINT ["java","-jar","/app.jar"]
