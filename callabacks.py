import torch
from torch.utils.tensorboard import SummaryWriter
from catalyst.core import Callback, CallbackOrder
from sklearn.metrics import balanced_accuracy_score

class BalancedAccuracyCallback(Callback):
    def __init__(self):
        super().__init__(CallbackOrder.Metric)

    def on_batch_end(self, runner: "IRunner") -> None:
        y_true = runner.input["targets"].to("cpu").numpy()
        y_pred = runner.output["preds"].to("cpu").numpy()
        runner.batch_metrics["balanced_accuracy_score"] = balanced_accuracy_score(y_true, y_pred)



class LogPRCurve(Callback):
    def __init__(self, log_dir: str = None):
        super().__init__(CallbackOrder.External)
        self.tensorboard_probs = []
        self.tensorboard_labels = []
        self.writer = SummaryWriter(log_dir)

    def on_loader_start(self, runner):
        self.tensorboard_probs = []
        self.tensorboard_labels = []

    def on_batch_end(self, runner):
        targets = runner.input["targets"]
        probs = torch.sigmoid(runner.output["logits"])
        self.tensorboard_probs.append(probs)
        self.tensorboard_labels.append(targets)

    def on_stage_end(self, runner):
        if runner.is_infer_stage:
            tensorboard_probs = torch.cat(self.tensorboard_probs).squeeze()
            tensorboard_labels = torch.cat(self.tensorboard_labels).squeeze()
            self.writer.add_pr_curve("precision_recall", tensorboard_labels, tensorboard_probs)


class LogGANProjection(Callback):
    def __init__(self, log_dir: str, tag: str, samples: int = 200):
        super().__init__(CallbackOrder.External)
        self.writer = SummaryWriter(log_dir)
        self.samples = samples
        self.tag = tag

    def on_stage_end(self, runner: "IRunner") -> None:
        embbedings_dict = runner.log_embeddings()
        embeddings = []
        metadata = []
        # Collect embeddings from loaders
        for key in embbedings_dict:
            loader_embbedings = embbedings_dict[key]["embedding"]
            embeddings.append(loader_embbedings)
            loader_labels = embbedings_dict[key]["labels"]
            labels = [f'{key}:{int(label)}' for label in loader_labels]
            metadata += labels

        # Collect embeddings from GAN
        random_latent_vectors, generated_labels = runner.model["generator"].sample_latent_vectors(self.samples)
        generated_embeddings = runner.model["generator"](random_latent_vectors).to('cpu')
        embeddings.append(generated_embeddings)
        gan_labels = [f'gan:{int(label)}' for label in generated_labels]
        metadata += gan_labels

        embeddings = torch.cat(embeddings)
        self.writer.add_embedding(embeddings, metadata=metadata,
                                  global_step=runner.epoch, tag=self.tag)

