FROM amazoncorretto:11-alpine
EXPOSE 5001
ENV PORT=5001
VOLUME /tmp
COPY target/*.jar app.jar
ENTRYPOINT ["java","-jar","/app.jar"]