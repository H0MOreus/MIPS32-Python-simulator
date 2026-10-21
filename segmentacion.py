class Segmentacion:
    def __init__(self, uProcesamiento, uControl, memInstrucciones, memDatos):
        self.up = uProcesamiento
        self.uc = uControl
        self.memI = memInstrucciones
        self.memD = memDatos

    def ciclo(self):
        self.wb()
        self.mem()
        self.ex()
        self.id()
        self.iF()

    

