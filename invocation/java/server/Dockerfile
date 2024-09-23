FROM amazoncorretto:11-alpine
EXPOSE 5002
ENV PORT=5002
VOLUME /tmp
COPY target/*.jar app.jar
ENTRYPOINT ["java","-jar","/app.jar"]