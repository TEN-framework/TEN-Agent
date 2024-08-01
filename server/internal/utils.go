package internal

import (
	"reflect"
)

func getFieldValue(req any, fieldName string) any {
	v := reflect.ValueOf(req)
	if v.Kind() == reflect.Ptr {
		v = v.Elem()
	}

	field := v.FieldByName(fieldName)

	if field.IsValid() {
		switch field.Kind() {
		case reflect.Bool:
			return field.Bool()
		case reflect.Float32:
			return float32(field.Float())
		case reflect.Float64:
			return field.Float()
		case reflect.Int:
			return field.Int()
		case reflect.Int32:
			return int(field.Int())
		case reflect.Int64:
			return field.Int()
		case reflect.Uint32:
			return field.Uint()
		case reflect.Uint64:
			return field.Uint()
		case reflect.String:
			return field.String()
		}
	}

	return nil
}
