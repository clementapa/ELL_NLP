from model.model import Model
import torch
import torch.optim as optim
import pytorch_lightning as pl


class MultiRegression(pl.LightningModule):
    def __init__(self, config):
        super(MultiRegression, self).__init__()

        self.config = config

        self.lr = config.lr
        self.batch_size = config.batch_size

        self.model = Model(config.name_model, config.nb_of_linears)

        # freeze backbone for fine tuned
        if config.freeze_backbone:
            print("Freezing features extractor")
            for param in self.model.features_extractor.base_model.parameters():
                param.requires_grad = False

        self.labels = [
            "cohesion",
            "syntax",
            "vocabulary",
            "phraseology",
            "grammar",
            "conventions",
        ]

    def configure_optimizers(self):
        """defines model optimizer"""
        out_dict = {}
        out_dict["optimizer"] = optim.Adam(
            self.model.parameters(), lr=self.lr, weight_decay=self.config.weight_decay
        )
        if self.config.scheduler != None:
            if self.config.scheduler == "CosineAnnealingLR":
                out_dict["scheduler"] = optim.lr_scheduler.CosineAnnealingLR(
                    out_dict["optimizer"], self.config.T_max
                )
            elif self.config.scheduler == "StepLR":
                out_dict["scheduler"] = optim.lr_scheduler.StepLR(
                    out_dict["optimizer"], self.config.step_size_scheduler
                )
            else:
                raise NotImplementedError(
                    f"{self.config.scheduler} scheduler not supported"
                )
        return out_dict

    def forward(self, x):
        outputs = self.model(x)
        return outputs

    def training_step(self, batch, batch_idx):
        """needs to return a loss from a single batch"""
        losses, preds = self._get_preds_loss_accuracy(batch)

        # Log loss and metric
        self.log("train/loss", losses.mean())

        # for i, name in enumerate(self.labels):
        #     self.log(f"train/{name}_loss", losses[i])

        return {"loss": losses.mean(), "preds": preds.detach()}

    def validation_step(self, batch, batch_idx):
        """used for logging metrics"""
        losses, preds = self._get_preds_loss_accuracy(batch)

        # Log loss and metric
        self.log("val/loss", losses.mean())

        # for i, name in enumerate(self.labels):
        #     self.log(f"val/{name}_loss", losses[i])

        # Let's return preds to use it in a custom callback
        return {"preds": preds}

    def predict_step(self, batch, batch_idx):
        inputs = batch
        preds = self(inputs)
        return preds
        
    def loss_fn(self, outputs, targets):
        """https://www.kaggle.com/competitions/feedback-prize-english-language-learning/discussion/348985"""
        assert outputs.shape == targets.shape

        colwise_mse = torch.mean(torch.square(targets - outputs), dim=0)
        loss = torch.mean(torch.sqrt(colwise_mse), dim=0)
        return loss

    def _get_preds_loss_accuracy(self, batch):
        """convenience function since train/valid/test steps are similar"""
        inputs, targets = batch
        preds = self(inputs)

        loss = self.loss_fn(preds, targets["labels"])

        return loss, preds
