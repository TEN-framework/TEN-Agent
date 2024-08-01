package internal

import (
	"fmt"
	"reflect"
)

func getFieldValue(req interface{}, fieldName string) string {
	v := reflect.ValueOf(req)
	field := v.FieldByName(fieldName)

	if field.IsValid() {
		switch field.Kind() {
		case reflect.String:
			return field.String()
		case reflect.Uint32:
			return fmt.Sprintf("%d", field.Uint())
		}
	}

	return ""
}
