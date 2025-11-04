set -euo pipefail

TAG=${GITHUB_SHA::7}
IMAGE_REF="${{ secrets.ACR_LOGIN_SERVER }}"/${IMAGE_NAME}:${TAG}

DB_CONN="${{ secrets.DB_URL }}"

az containerapp secret set \
  --name ${{ secrets.CONTAINERAPP_NAME }} \
  --resource-group ${{ secrets.RESOURCE_GROUP }} \
  --secrets db-url="${DB_CONN}"

az containerapp update \
  --name ${{ secrets.CONTAINERAPP_NAME }} \
  --resource-group ${{ secrets.RESOURCE_GROUP }} \
  --image "${IMAGE_REF}" \
  --set-env-vars API_URL=${{ secrets.PUBLIC_API_URL }} \
                 SUNEDITOR_TOOLBAR_ENABLED=0 \
                 DB_URL=secretref:db-url

az containerapp revision list \
  --name ${{ secrets.CONTAINERAPP_NAME }} \
  --resource-group ${{ secrets.RESOURCE_GROUP }} \
  --query "[?properties.active==\`true\`].name" -o tsv | while read REV; do
  if [ -n "$REV" ]; then
    echo "Deactivating revision $REV"
    az containerapp revision deactivate \
      --name ${{ secrets.CONTAINERAPP_NAME }} \
      --resource-group ${{ secrets.RESOURCE_GROUP }} \
      --revision "$REV"
  fi
done

az containerapp revision list \
  --name ${{ secrets.CONTAINERAPP_NAME }} \
  --resource-group ${{ secrets.RESOURCE_GROUP }} \
  --query "[?properties.latestRevision==\`true\`].name" -o tsv | while read REV; do
  if [ -n "$REV" ]; then
    echo "Activating latest revision $REV"
    az containerapp revision activate \
      --name ${{ secrets.CONTAINERAPP_NAME }} \
      --resource-group ${{ secrets.RESOURCE_GROUP }} \
      --revision "$REV"
  fi
done

az containerapp revision activate \
  --name ${{ secrets.CONTAINERAPP_NAME }} \
  --resource-group ${{ secrets.RESOURCE_GROUP }} \
  --revision $(az containerapp revision list --name ${{ secrets.CONTAINERAPP_NAME }} --resource-group ${{ secrets.RESOURCE_GROUP }} --query "[?properties.latestRevision==\`true\`].name" -o tsv | head -n 1)

rm update_containerapp.sh
