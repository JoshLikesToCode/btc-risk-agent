from pydantic import BaseModel, Field


class TxIO(BaseModel):
    address: str | None  # None for OP_RETURN / non-standard scripts
    value: int  # satoshis


class Tx(BaseModel):
    txid: str
    block_time: int | None = None
    inputs: list[TxIO] = Field(default_factory=list)
    outputs: list[TxIO] = Field(default_factory=list)

    @property
    def input_addresses(self) -> set[str]:
        return {i.address for i in self.inputs if i.address}

    @property
    def output_addresses(self) -> set[str]:
        return {o.address for o in self.outputs if o.address}


class AddressSummary(BaseModel):
    address: str
    tx_count: int
    total_received: int
    total_sent: int
