#!/bin/bash
echo "🔍 ARIIA Deployment Report" > deployment_report.txt
echo "========================" >> deployment_report.txt
date >> deployment_report.txt

echo -e "\n1. Docker Processes:" >> deployment_report.txt
docker ps -a >> deployment_report.txt

echo -e "\n2. Internal Connectivity (localhost):" >> deployment_report.txt
curl -v http://localhost:8000/health 2>> deployment_report.txt

echo -e "\n3. Container Logs (Last 50 lines - ariia_core):" >> deployment_report.txt
docker logs --tail 50 ariia_core 2>&1 >> deployment_report.txt

echo -e "\n4. Redis Logs (Last 20 lines):" >> deployment_report.txt
docker logs --tail 20 ariia_redis 2>&1 >> deployment_report.txt

echo -e "\n========================" >> deployment_report.txt
echo "✅ Report generated: deployment_report.txt"
cat deployment_report.txt
