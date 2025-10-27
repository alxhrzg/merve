- Create parameterisable registry service (default GH registry, optional ECR config)

        - name: 🔑 Configure AWS credentials
                uses: aws-actions/configure-aws-credentials@v5
                with:
                role-to-assume: ${{ vars.AWS_DEV_ROLE_ARN }}
                role-session-name: GitHubActions-cdk-synth-${{ needs.setup.outputs.environment }}
                aws-region: ${{ env.AWS_REGION }}
                
            - name: 🔐 Login to Amazon ECR
                uses: aws-actions/amazon-ecr-login@v2
                with:
                registries: '123456789012'

        
- Create parameterisable S2 bucket for artefacts
- Update trade-likelihood repo with freshest mlserver.yaml and predictor classes
- Move SageMaker notebook to GH backend!