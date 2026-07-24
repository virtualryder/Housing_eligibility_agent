"""IdentityStack — federation-ready Cognito, NO built-in users (P0-6).

Production identity is a federated enterprise IdP (Okta / Entra ID / Ping) through this pool — see
docs/IdP-Federation-Reference.md. This stack deliberately creates ZERO users and ships ZERO passwords;
sandbox demo users exist only in the legacy shell path behind an explicit SANDBOX_IDENTITY=1
acknowledgment."""
import aws_cdk as cdk
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class IdentityStack(cdk.Stack):
    def __init__(self, scope: Construct, cid: str, *, prefix: str, **kw):
        super().__init__(scope, cid, **kw)
        self.pool = cognito.UserPool(
            self, "Pool", user_pool_name=f"{prefix}-identity",
            self_sign_up_enabled=False,
            mfa=cognito.Mfa.OPTIONAL,   # REQUIRED under P1-1 with federation/conditional access
            password_policy=cognito.PasswordPolicy(
                min_length=14, require_lowercase=True, require_uppercase=True,
                require_digits=True, require_symbols=True),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.client = self.pool.add_client(
            "GatewayClient", user_pool_client_name=f"{prefix}-gw",
            auth_flows=cognito.AuthFlow(user_srp=True),   # no USER_PASSWORD_AUTH in the CDK path
            generate_secret=False,
        )
        cognito.CfnUserPoolGroup(self, "ReviewerGroup", user_pool_id=self.pool.user_pool_id,
                                 group_name="housing_specialist",
                                 description="Qualified housing specialists (Cedar role group)")
        cdk.CfnOutput(self, "UserPoolId", value=self.pool.user_pool_id)
        cdk.CfnOutput(self, "ClientId", value=self.client.user_pool_client_id)
        cdk.CfnOutput(self, "FederationNote",
                      value="No users are created by IaC; federate the enterprise IdP "
                            "(docs/IdP-Federation-Reference.md) or create operators out-of-band.")
