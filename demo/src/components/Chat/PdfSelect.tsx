"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { FileTextIcon } from "lucide-react"

import { OptionType, IPdfData } from "@/types"
import {
  apiGetDocumentList,
  apiUpdateDocument,
  useAppSelector,
  genUUID,
} from "@/common"
import { toast } from "sonner"

export default function PdfSelect() {
  const options = useAppSelector((state) => state.global.options)
  const { channel, userId } = options
  const [pdfOptions, setPdfOptions] = React.useState<OptionType[]>([])
  const [selectedPdf, setSelectedPdf] = React.useState<string>("")
  const agentConnected = useAppSelector((state) => state.global.agentConnected)

  React.useEffect(() => {
    if (agentConnected) {
      getPDFOptions()
    }
  }, [agentConnected])

  const getPDFOptions = async () => {
    const res = await apiGetDocumentList()
    setPdfOptions(
      res.data.map((item: any) => {
        return {
          value: item.collection,
          label: item.file_name,
        }
      }),
    )
    setSelectedPdf("")
  }

  const onUploadSuccess = (data: IPdfData) => {
    setPdfOptions([
      ...pdfOptions,
      {
        value: data.collection,
        label: data.fileName,
      },
    ])
    setSelectedPdf(data.collection)
  }

  const onSelectPdf = async (val: string) => {
    const item = pdfOptions.find((item) => item.value === val)
    if (!item) {
      //   return message.error("Please select a PDF file")
      return
    }
    setSelectedPdf(val)
    await apiUpdateDocument({
      collection: val,
      fileName: item.label,
      channel,
    })
  }

  return (
    <>
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm" className="w-fit bg-transparent">
            <FileTextIcon />
            PDF
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Upload & Select PDF</DialogTitle>
          </DialogHeader>
          <UploadPdf onSuccess={onUploadSuccess} />
          <div className="mt-4">
            <Select
              value={selectedPdf}
              onValueChange={onSelectPdf}
              disabled={!agentConnected}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a PDF file" />
              </SelectTrigger>
              <SelectContent>
                {pdfOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

export function UploadPdf({
  onSuccess,
}: {
  onSuccess?: (data: IPdfData) => void
}) {
  const agentConnected = useAppSelector((state) => state.global.agentConnected)
  const options = useAppSelector((state) => state.global.options)
  const { channel, userId } = options
  const [uploading, setUploading] = React.useState(false)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!agentConnected) {
      // Use browser alert since we don't have antd message
      toast.error("Please connect to agent first")
      return
    }

    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)

    const formData = new FormData()
    formData.append("file", file)
    formData.append("channel_name", channel)
    formData.append("uid", String(userId))
    formData.append("request_id", genUUID())

    try {
      const response = await fetch("/api/vector/document/upload", {
        method: "POST",
        body: formData,
      })
      const data = await response.json()

      if (data.code === "0") {
        toast.success(`Upload ${file.name} success`)
        const { collection, file_name } = data.data
        onSuccess?.({
          fileName: file_name,
          collection,
        })
      } else {
        toast.info(data.msg)
      }
    } catch (err) {
      toast.error(`Upload ${file.name} failed`)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <Label htmlFor="pdf-upload" className="cursor-pointer">
        <Input
          id="pdf-upload"
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={handleUpload}
          disabled={uploading}
        />
        <Button variant="outline" size="sm" disabled={uploading} asChild>
          <span>{uploading ? "Uploading..." : "Upload PDF"}</span>
        </Button>
      </Label>
    </div>
  )
}
