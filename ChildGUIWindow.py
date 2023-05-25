###########################################################################
## Four classes that build child GUI for the main GUI                    ##
## Click 'Trajectory setting' button to open SineGUI, RampGUI, RandomGUI ##
## Click 'User Infomation' button to open UserInfoGUI                    ##
###########################################################################

from PyQt5 import QtWidgets, QtCore


class UserInfoGUI(QtWidgets.QDialog):

    def __init__(self,*args, **kwargs):
        super(UserInfoGUI, self).__init__(*args, **kwargs)

        self.setWindowTitle('User Infomation')

        #### Build up the layout: 1. Create text (QLabel) and input blank (QLineEdit) or dropbox (QComboBox) ####
        layout = QtWidgets.QVBoxLayout(self)
        self.label1 = QtWidgets.QLabel(self)
        self.label1.setText("Body Weight (kg)：")
        self.Weight = QtWidgets.QLineEdit(self)
        self.Weight.setText("0")
        self.label2 = QtWidgets.QLabel(self)
        self.label2.setText("Height (cm)：")
        self.Height = QtWidgets.QLineEdit(self)
        self.Height.setText("0")
        self.label3 = QtWidgets.QLabel(self)
        self.label3.setText("Gender：")
        self.gender = QtWidgets.QComboBox()        ## Dropbox ##
        self.gender.addItem("Male")
        self.gender.addItem("Female")
        self.gender.currentIndexChanged.connect(self.genderchange)
        self.label4 = QtWidgets.QLabel(self)
        self.label4.setText("Assistance (%)：")
        self.assistance = QtWidgets.QLineEdit(self)
        self.assistance.setText("0")
        #### Build up the layout: 2. Combine everything on the canvas ####
        layout.addWidget(self.label1)
        layout.addWidget(self.Weight)
        layout.addWidget(self.label2)
        layout.addWidget(self.Height)
        layout.addWidget(self.label3)
        layout.addWidget(self.gender)
        layout.addWidget(self.label4)
        layout.addWidget(self.assistance)

        #### Add 'OK', 'Cancel' button at the end ####
        buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,QtCore.Qt.Horizontal,self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.GenderText = 'M'

    #### Dropbox Selection ####
    def genderchange(self, i):
        if i == 0:
            self.GenderText = 'M'
        elif i == 1:
            self.GenderText = 'F'

    #### Function to send the input data to main GUI. Important: the format is str ####
    def getResult(self):
        dialog=UserInfoGUI()
        result=dialog.exec_()
        return (dialog.Weight.text(),dialog.Height.text(),dialog.GenderText,dialog.assistance.text(),result)


class SineGUI(QtWidgets.QDialog):

    def __init__(self,*args, **kwargs):
        super(SineGUI, self).__init__(*args, **kwargs)

        self.setWindowTitle('Sine')

        layout = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel(self)
        self.label.setText("Sine Wave Parameter：")
        self.label1 = QtWidgets.QLabel(self)
        self.label1.setText("Amplitude：")
        self.sinAmp = QtWidgets.QLineEdit(self)
        self.sinAmp.setText("10")
        self.label2 = QtWidgets.QLabel(self)
        self.label2.setText("Frequency：")
        self.sinFre = QtWidgets.QLineEdit(self)
        self.sinFre.setText("0.1")
        self.label3 = QtWidgets.QLabel(self)
        self.label3.setText("DC Offset：")
        self.sinOffset = QtWidgets.QLineEdit(self)
        self.sinOffset.setText("0")
        layout.addWidget(self.label)
        layout.addWidget(self.label1)
        layout.addWidget(self.sinAmp)
        layout.addWidget(self.label2)
        layout.addWidget(self.sinFre)
        layout.addWidget(self.label3)
        layout.addWidget(self.sinOffset)

        buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,QtCore.Qt.Horizontal,self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getResult(self):
        dialog=SineGUI()
        result=dialog.exec_()
        return (dialog.sinAmp.text(),dialog.sinFre.text(),dialog.sinOffset.text(),result)

    def getResult_n(self):
        dialog=self
        result=dialog.exec_()
        return (self.sinAmp.text(), self.sinFre.text(), self.sinOffset.text(), result)


class RampGUI(QtWidgets.QDialog):

    def __init__(self,*args, **kwargs):
        super(RampGUI, self).__init__(*args, **kwargs)

        self.setWindowTitle('Ramp')

        layout = QtWidgets.QVBoxLayout(self)
        self.rlabel = QtWidgets.QLabel(self)
        self.rlabel.setText("Ramp Wave Parameter：")
        self.rlabel1 = QtWidgets.QLabel(self)
        self.rlabel1.setText("Amplitude1：")
        self.rampAmp1 = QtWidgets.QLineEdit(self)
        self.rampAmp1.setText("-10")
        self.rlabel2 = QtWidgets.QLabel(self)
        self.rlabel2.setText("Amplitude2：")
        self.rampAmp2 = QtWidgets.QLineEdit(self)
        self.rampAmp2.setText("10")
        self.rlabel3 = QtWidgets.QLabel(self)
        self.rlabel3.setText("Time1：")
        self.rampTime2 = QtWidgets.QLineEdit(self)
        self.rampTime2.setText("5")

        self.rlabel4 = QtWidgets.QLabel(self)
        self.rlabel4.setText("Time2：")
        self.rampTime3 = QtWidgets.QLineEdit(self)
        self.rampTime3.setText("8")

        self.rlabel5 = QtWidgets.QLabel(self)
        self.rlabel5.setText("Time3：")
        self.rampTime4 = QtWidgets.QLineEdit(self)
        self.rampTime4.setText("13")

        self.rlabel6 = QtWidgets.QLabel(self)
        self.rlabel6.setText("Time4：")
        self.rampTime5 = QtWidgets.QLineEdit(self)
        self.rampTime5.setText("16")

        layout.addWidget(self.rlabel)
        layout.addWidget(self.rlabel1)
        layout.addWidget(self.rampAmp1)
        layout.addWidget(self.rlabel2)
        layout.addWidget(self.rampAmp2)

        layout.addWidget(self.rlabel3)
        layout.addWidget(self.rampTime2)
        layout.addWidget(self.rlabel4)
        layout.addWidget(self.rampTime3)
        layout.addWidget(self.rlabel5)
        layout.addWidget(self.rampTime4)
        layout.addWidget(self.rlabel6)
        layout.addWidget(self.rampTime5)

        buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,QtCore.Qt.Horizontal,self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getResult(self):
        dialog=RampGUI()
        result=dialog.exec_()
        return (float(dialog.rampAmp1.text()),float(dialog.rampAmp2.text()),float(dialog.rampTime2.text()),float(dialog.rampTime3.text()),float(dialog.rampTime4.text()),float(dialog.rampTime5.text()),result)

    def getResult_n(self):
        dialog=self
        result=dialog.exec_()
        return (float(self.rampAmp1.text()),float(self.rampAmp2.text()),float(self.rampTime2.text()),float(self.rampTime3.text()),float(self.rampTime4.text()),float(self.rampTime5.text()),result)


class RandomGUI(QtWidgets.QDialog):

    def __init__(self,*args, **kwargs):
        super(RandomGUI, self).__init__(*args, **kwargs)

        self.setWindowTitle('Random')

        layout = QtWidgets.QVBoxLayout(self)
        self.label1 = QtWidgets.QLabel(self)
        self.label1.setText("Amplitude：")
        self.ranAmp = QtWidgets.QLineEdit(self)
        self.ranAmp.setText("10")

        layout.addWidget(self.label1)
        layout.addWidget(self.ranAmp)

        buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,QtCore.Qt.Horizontal,self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def getResult(self):
        dialog=RandomGUI()
        result=dialog.exec_()
        return (dialog.ranAmp.text(),result)

    def getResult_n(self):
        dialog=self
        result=dialog.exec_()
        return (self.ranAmp.text(),result)


class ResetGUI(QtWidgets.QDialog):

    def __init__(self,*args, **kwargs):
        super(ResetGUI, self).__init__(*args, **kwargs)

        self.setWindowTitle('Random')

        layout = QtWidgets.QVBoxLayout(self)
        self.label1 = QtWidgets.QLabel(self)
        self.label1.setText("Neural:")
        self.posNeu = QtWidgets.QLineEdit(self)
        self.posNeu.setText("10")

        self.label2 = QtWidgets.QLabel(self)
        self.label2.setText("DF:")
        self.posDF = QtWidgets.QLineEdit(self)
        self.posDF.setText("-9")

        self.label3 = QtWidgets.QLabel(self)
        self.label3.setText("PF:")
        self.posPF = QtWidgets.QLineEdit(self)
        self.posPF.setText("20")

        self.label4 = QtWidgets.QLabel(self)
        self.label4.setText("TA MVC:")
        self.TAMVC = QtWidgets.QLineEdit(self)
        self.TAMVC.setText("1")

        self.label5 = QtWidgets.QLabel(self)
        self.label5.setText("GM MVC:")
        self.GMMVC = QtWidgets.QLineEdit(self)
        self.GMMVC.setText("1")

        layout.addWidget(self.label1)
        layout.addWidget(self.posNeu)
        layout.addWidget(self.label2)
        layout.addWidget(self.posDF)
        layout.addWidget(self.label3)
        layout.addWidget(self.posPF)
        layout.addWidget(self.label4)
        layout.addWidget(self.TAMVC)
        layout.addWidget(self.label5)
        layout.addWidget(self.GMMVC)

        buttons=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel,QtCore.Qt.Horizontal,self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def getResult(self):
        dialog = ResetGUI()
        result = dialog.exec_()
        self.posNEU_f = float(self.posNeu.text())
        self.posMAX_f = float(self.posNeu.text()) + float(self.posDF.text())
        self.posMIN_f = float(self.posNeu.text()) + float(self.posPF.text())
        self.TAMVC_f = float(self.TAMVC.text())
        self.GMMVC_f = float(self.GMMVC.text())
        return (self.posNEU_f, self.posMAX_f, self.posMIN_f, self.TAMVC_f, self.GMMVC_f, result)


    def getResult_n(self):
        dialog = self
        result = dialog.exec_()
        self.posNEU_f = float(self.posNeu.text())
        self.posMAX_f = float(self.posNeu.text()) + float(self.posDF.text())
        self.posMIN_f = float(self.posNeu.text()) + float(self.posPF.text())
        self.TAMVC_f = float(self.TAMVC.text())
        self.GMMVC_f = float(self.GMMVC.text())
        return (self.posNEU_f, self.posMAX_f, self.posMIN_f, self.TAMVC_f, self.GMMVC_f, result)
